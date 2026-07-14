# 星眠 SmartSleep 智能客服 Agent

> **求职作品集**：智能客服 Agent + **自建 FastAPI 后端**（会话 / 日志 / Trace / HTTP 订单工具）+ Golden Set 评测。  
> 本仓库已替换旧版「仅 Dify 四分支工作流 / dify-workflow.yml」项目；以可运行后端与可复现评测为主资产。  
> 仓库：https://github.com/iig64625-bot/kefuzhinengti

[![Dify](https://img.shields.io/badge/Dify-Chatflow-blue)](https://dify.ai)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%2BSQLite-009688)]()
[![Eval](https://img.shields.io/badge/Eval-20%20Golden-orange)]()

## 项目简介

**星眠 SmartSleep** 是虚构电商品牌的 7×24 智能客服。系统工程分层：

| 层 | 职责 | 资产归属 |
|----|------|----------|
| Dify Chatflow | 分流、RAG 体验、HITL | 编排（可替换） |
| FastAPI 后端 | 会话、消息、Trace、访问日志、工单、Mock OMS | **自有** |
| 评测脚本 | Golden Set 20 题 → 准确率 / 兜底率 / Trace | **可证明** |

面试时可说：换 Dify 账号不会丢后端数据库、工具契约与评测数字。

## 技术架构

```
用户 → Dify Chatflow（体验层）
         ├─ 知识检索 + LLM
         ├─ HTTP 工具 → 自建 /api/v1/tools/query_order
         └─ 失败 → 转人工 / Ticket
              ↕
       FastAPI + SQLite
         ├─ POST /api/v1/chat（本地 RAG 可独立 demo）
         ├─ conversations / messages / trace_events / tickets
         └─ Mock OMS（timeout / 500 混沌 → 重试 → 降级）
```

## 简历可写数字（自动生成）

```bash
backend\.venv\Scripts\python tests\run_eval.py
```

最新结果（见 [docs/eval-report.md](docs/eval-report.md)）：

| 指标 | 目标 | 实际 |
|------|------|------|
| 答案准确率（加权） | ≥80% | **见 eval-report** |
| 检索命中率 | ≥85% | **见 eval-report** |
| 安全合规（Q19/Q20） | 100% | **见 eval-report** |
| Golden Set | 20 题 | **见 eval-report** |
| 工具闭环 | 重试+降级 | force_fail=500 → 3 次后 degrade |

## 快速启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

- Swagger：http://127.0.0.1:8000/docs  
- 说明：[backend/README.md](backend/README.md)  
- Dify 接 HTTP 工具：[docs/dify-http-tool.md](docs/dify-http-tool.md)

### 演示三连

```bash
# 1）正常查单
curl -X POST http://127.0.0.1:8000/api/v1/chat -H "Content-Type: application/json" -d "{\"query\":\"帮我查订单 PP20260713001234 物流\"}"

# 2）工具失败降级
curl "http://127.0.0.1:8000/api/v1/tools/query_order?order_id=PP20260713001234&force_fail=500"

# 3）看 Trace（把 conversation_id 换成上一步返回值）
curl http://127.0.0.1:8000/api/v1/conversations/{id}/traces
```

## 项目结构

```
kefuzhinengti/  (本仓库根目录 = StarSleep Agent)
├── backend/                 # FastAPI：会话 / 日志 / Trace / OMS / 工具门面
├── dify/                    # OpenAPI + HTTP 接线说明
├── docs/                    # 架构、评测报告、安全、工具闭环
├── knowledge-base/          # 4 类 Markdown 知识库
├── prompts/                 # System / User Prompt
└── tests/
    ├── golden_set.json      # 机器可读 20 题
    ├── golden-questions.md
    └── run_eval.py          # 产出 docs/eval-report.md
```

## 对照面试视频的三点

1. **系统工程**：API + SQLite 会话 + request logs + Trace + Ticket（不只是 Dify 编排）  
2. **可证明**：`run_eval.py` → 准确率 / 通过题数 / 安全合规；可附 JSON  
3. **真工具闭环**：HTTP `query_order` + timeout/retry + `degraded` 降级转人工  

## 安全

见 [docs/safety-policy.md](docs/safety-policy.md)。危险品建议「继续用」、代查他人订单必须拦截（Q19/Q20）。
