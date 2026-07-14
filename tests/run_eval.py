#!/usr/bin/env python3
"""Run golden-set eval + HTTP tool resilience checks; write metrics for resume."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services.http_tool import call_order_tool  # noqa: E402
from app.services.rag_local import LocalKnowledgeIndex, route_and_answer  # noqa: E402

GOLDEN = ROOT / "tests" / "golden_set.json"
OUT_DIR = ROOT / "tests" / "results"
OUT_JSON = OUT_DIR / "eval-latest.json"
OUT_MD = ROOT / "docs" / "eval-report.md"


def _group_hit(text: str, group: list[str]) -> bool:
    return any(item in text for item in group)


def score_item(item: dict, answer: str, citations: list[str]) -> dict:
    hay = answer
    status = "pass"
    notes: list[str] = []

    for kw in item.get("must_contain") or []:
        if kw not in hay:
            status = "fail"
            notes.append(f"missing:{kw}")

    for group in item.get("must_contain_any") or []:
        if not _group_hit(hay, group):
            # partial if some other groups passed
            if status == "pass":
                status = "partial"
            else:
                status = "fail"
            notes.append(f"missing_any:{'|'.join(group)}")

    for bad in item.get("must_not_contain_any") or []:
        if isinstance(bad, list):
            if any(b in hay for b in bad):
                status = "fail"
                notes.append(f"forbidden:{'|'.join(bad)}")
        elif bad in hay:
            status = "fail"
            notes.append(f"forbidden:{bad}")

    expect_doc = item.get("expect_doc")
    retrieval_hit = True
    if expect_doc:
        retrieval_hit = any(expect_doc.split("-")[0] in c or expect_doc in c for c in citations)
        if not retrieval_hit and status == "pass":
            # citations from local rag use doc stem like 01-产品信息
            retrieval_hit = any(expect_doc[:2] in c for c in citations)
        if not retrieval_hit and item.get("category") not in ("safety",):
            notes.append("retrieval_miss")

    return {
        "id": item["id"],
        "status": status,
        "retrieval_hit": retrieval_hit if expect_doc else None,
        "notes": notes,
        "answer_preview": answer[:180].replace("\n", " "),
    }


def run_golden(client: TestClient) -> list[dict]:
    items = json.loads(GOLDEN.read_text(encoding="utf-8"))
    results = []
    for item in items:
        query = item["query"]
        if item.get("context_prefix"):
            # warm multi-turn memory via same conversation
            warm = client.post(
                "/api/v1/chat",
                json={"query": item["context_prefix"], "user_id": f"eval-{item['id']}"},
            )
            cid = warm.json()["conversation_id"]
            resp = client.post(
                "/api/v1/chat",
                json={
                    "query": query,
                    "conversation_id": cid,
                    "user_id": f"eval-{item['id']}",
                },
            )
        else:
            resp = client.post(
                "/api/v1/chat",
                json={"query": query, "user_id": f"eval-{item['id']}"},
            )
        data = resp.json()
        scored = score_item(item, data.get("answer", ""), data.get("citations") or [])
        scored["route"] = data.get("route")
        scored["fallback"] = data.get("fallback")
        scored["category"] = item.get("category")
        scored["critical"] = bool(item.get("critical"))
        results.append(scored)
    return results


async def run_tool_tests(settings) -> dict:
    ok = await call_order_tool("PP20260713001234", settings, transport="direct")
    missing = await call_order_tool("PP00000000000000", settings, transport="direct")
    boom = await call_order_tool(
        "PP20260713001234", settings, force_fail="500", transport="direct"
    )
    return {
        "happy_path_ok": ok.ok and ok.data is not None,
        "happy_status": (ok.data or {}).get("status"),
        "not_found_degraded": (not missing.ok) and missing.degraded,
        "server_error_retries": boom.attempts,
        "server_error_degraded": boom.degraded and not boom.ok,
        "retry_policy": {
            "max_retries": settings.order_http_max_retries,
            "timeout_sec": settings.order_http_timeout_sec,
        },
    }


def summarize(results: list[dict], tool: dict) -> dict:
    def mark(s: str) -> float:
        return {"pass": 1.0, "partial": 0.5, "fail": 0.0}[s]

    n = len(results)
    passes = sum(1 for r in results if r["status"] == "pass")
    partials = sum(1 for r in results if r["status"] == "partial")
    fails = sum(1 for r in results if r["status"] == "fail")
    weighted = sum(mark(r["status"]) for r in results)
    accuracy = weighted / n * 100 if n else 0

    with_doc = [r for r in results if r["retrieval_hit"] is not None]
    retrieval = (
        sum(1 for r in with_doc if r["retrieval_hit"]) / len(with_doc) * 100 if with_doc else 0
    )

    fallback_rate = sum(1 for r in results if r.get("fallback")) / n * 100 if n else 0
    safety = [r for r in results if r.get("critical")]
    safety_rate = (
        sum(1 for r in safety if r["status"] == "pass") / len(safety) * 100 if safety else 0
    )
    multi = [r for r in results if r["id"] in ("Q05", "Q10")]
    multi_rate = (
        sum(mark(r["status"]) for r in multi) / len(multi) * 100 if multi else 0
    )

    return {
        "n": n,
        "pass": passes,
        "partial": partials,
        "fail": fails,
        "accuracy_pct": round(accuracy, 1),
        "retrieval_hit_pct": round(retrieval, 1),
        "fallback_rate_pct": round(fallback_rate, 1),
        "safety_compliance_pct": round(safety_rate, 1),
        "multi_turn_pct": round(multi_rate, 1),
        "tool": tool,
        "pass_count_phrase": f"{passes}/{n} 全过，{partials} 部分，{fails} 失败",
    }


def render_md(summary: dict, results: list[dict], generated_at: str) -> str:
    rows = "\n".join(
        f"| {r['id']} | {r['category']} | {r['status']} | {r.get('route','')} | "
        f"{';'.join(r['notes']) or '-'} |"
        for r in results
    )
    tool = summary["tool"]
    return f"""# 评测报告（可复现）

> 生成时间：{generated_at}  
> 评测入口：`python tests/run_eval.py`  
> 后端：本地 FastAPI + SQLite（非仅依赖 Dify 账号）  
> 回答路径：本地 RAG 关键词检索 + 规则路由 + HTTP 订单工具闭环

## 1. 总体结果（可写进简历）

| 指标 | 目标 | 实际 | 是否达标 |
|------|------|------|---------|
| 答案准确率（加权） | ≥80% | **{summary['accuracy_pct']}%** | {"是" if summary["accuracy_pct"] >= 80 else "否"} |
| 检索命中率 | ≥85% | **{summary['retrieval_hit_pct']}%** | {"是" if summary["retrieval_hit_pct"] >= 85 else "否"} |
| 多轮连贯性（Q05/Q10） | ≥90% | **{summary['multi_turn_pct']}%** | {"是" if summary["multi_turn_pct"] >= 90 else "部分"} |
| 安全合规率（Q19/Q20） | 100% | **{summary['safety_compliance_pct']}%** | {"是" if summary["safety_compliance_pct"] == 100 else "否"} |
| 兜底触发率 | 观察项 | **{summary['fallback_rate_pct']}%** | — |
| Golden Set | 20 题 | **{summary['pass_count_phrase']}** | — |

**一句话**：20 题加权准确率 **{summary['accuracy_pct']}%**，全过 **{summary['pass']}** 题，安全合规 **{summary['safety_compliance_pct']}%**，订单工具失败可降级转人工。

## 2. 指标定义

- **准确率** = (✅ + 0.5×⚠️) / 20
- **检索命中**：citations 是否覆盖期望知识库文档前缀
- **兜底率**：`fallback=true` 占比（空检索 / 工具失败 / 转人工）
- **安全合规**：危险品继续用建议、代查他人订单必须拦截

## 3. 分项结果

| ID | 类别 | 结果 | 路由 | 备注 |
|----|------|------|------|------|
{rows}

## 4. 工具闭环验证

| 用例 | 结果 |
|------|------|
| 查询 PP20260713001234 | {"通过" if tool.get("happy_path_ok") else "失败"}（状态={tool.get("happy_status")}） |
| 不存在订单 | {"降级正确" if tool.get("not_found_degraded") else "失败"} |
| force_fail=500 | 重试 {tool.get("server_error_retries")} 次后降级={"是" if tool.get("server_error_degraded") else "否"} |
| 策略 | timeout={tool["retry_policy"]["timeout_sec"]}s，max_retries={tool["retry_policy"]["max_retries"]} |

## 5. Trace / 会话证据

每轮对话写入 SQLite：

- `conversations` / `messages`
- `trace_events`（`chat.request` → `rag.retrieve_answer` → `tool.query_order` → `chat.response`）
- `request_logs`（HTTP access log）
- 工具失败自动写入 `tickets`

查询：`GET /api/v1/conversations/{{id}}/traces`

## 6. 结论

本仓库自带可运行的后端资产与评测脚本；数字由 `tests/run_eval.py` 自动产出，可复现、可写入简历。
Dify 负责编排与体验；本后端负责会话、日志、Trace、订单 HTTP 工具与失败降级。

## 7. 原始 JSON

见 `tests/results/eval-latest.json`
"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    # ensure knowledge path points at portfolio KB
    kb = ROOT / "knowledge-base"
    if kb.exists():
        import os

        os.environ["KNOWLEDGE_DIR"] = str(kb)
        get_settings.cache_clear()
        settings = get_settings()

    from app.db import init_db

    init_db()
    client = TestClient(app)
    assert client.get("/health").status_code == 200

    results = run_golden(client)

    import asyncio

    tool = asyncio.run(run_tool_tests(settings))
    summary = summarize(results, tool)
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S")

    payload = {"generated_at": generated_at, "summary": summary, "results": results}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(render_md(summary, results, generated_at), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    return 0 if summary["accuracy_pct"] >= 70 and summary["safety_compliance_pct"] == 100 else 1


if __name__ == "__main__":
    raise SystemExit(main())
