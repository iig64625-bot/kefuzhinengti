# 星眠 SmartSleep 智能客服 Agent

基于 Dify Chatflow 与自建 FastAPI 后端的电商智能客服系统，覆盖产品咨询、使用售后、订单查询与退款政策。

[![Dify](https://img.shields.io/badge/Dify-Chatflow-blue)](https://dify.ai)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%2BSQLite-009688)]()
[![Eval](https://img.shields.io/badge/Eval-20%20Golden-orange)]()

## 项目简介

**星眠 SmartSleep** 是虚构电商品牌的 7×24 智能客服助手。用户用自然语言提问，系统自动检索知识库、必要时调用订单接口，并在无法可靠回答或高风险场景时转人工。

| 层级 | 职责 |
|------|------|
| Dify Chatflow | 意图分流、知识检索、对话体验、人工介入 |
| FastAPI 后端 | 会话与消息持久化、访问日志、调用 Trace、工单、Mock 订单服务 |
| 评测脚本 | 20 题 Golden Set，自动汇总准确率、检索命中率与工具降级结果 |

## 功能特性

- **知识问答**：产品型号对比、蓝牙/热敷排查、保修与包邮等 FAQ
- **订单查询**：HTTP 工具查询物流状态；超时与 5xx 自动重试，失败后降级转人工
- **会话与可观测**：SQLite 保存会话/消息；可按 `conversation_id` 回放 Trace
- **安全兜底**：过热异味等场景引导停用并联系热线；拒绝代查他人订单
- **离线评测**：一键跑通标准题集，结果写入 `docs/eval-report.md`

## 技术架构

```
用户 → Dify Chatflow（体验层）
         ├─ 知识检索 + LLM
         ├─ HTTP 工具 → /api/v1/tools/query_order
         └─ 失败 → 转人工 / Ticket
              ↕
       FastAPI + SQLite
         ├─ POST /api/v1/chat（也可脱离 Dify 独立运行）
         ├─ conversations / messages / trace_events / tickets
         └─ Mock OMS（支持 timeout / 500 等故障注入）
```

## 评测结果

```bash
backend\.venv\Scripts\python tests\run_eval.py
```

详见 [docs/eval-report.md](docs/eval-report.md)。最近一次离线结果摘要：

| 指标 | 目标 | 最近结果 |
|------|------|----------|
| 答案准确率（加权） | ≥80% | 100.0% |
| 检索命中率 | ≥85% | 93.8% |
| 安全合规（Q19/Q20） | 100% | 100.0% |
| Golden Set | 20 题 | 20/20 通过 |
| 订单工具失败降级 | 可重试后 degrade | force_fail=500 → 3 次后降级 |

## 快速开始

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

- API 文档：http://127.0.0.1:8000/docs  
- 后端说明：[backend/README.md](backend/README.md)  
- Dify HTTP 工具接线：[docs/dify-http-tool.md](docs/dify-http-tool.md)

### 常用接口示例

```bash
# 对话（含订单工具）
curl -X POST http://127.0.0.1:8000/api/v1/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"帮我查订单 PP20260713001234 物流\"}"

# 订单工具故障注入（演示重试与降级）
curl "http://127.0.0.1:8000/api/v1/tools/query_order?order_id=PP20260713001234&force_fail=500"

# 查看 Trace（替换为实际 conversation_id）
curl http://127.0.0.1:8000/api/v1/conversations/{id}/traces
```

### 示例订单号

| 订单号 | 状态 |
|--------|------|
| PP20260713001234 | 已发货 |
| PP20260712005678 | 待发货 |
| PP20260711009999 | 已完成 |

## 项目结构

```
├── backend/            # FastAPI：会话、日志、Trace、OMS、工具门面
├── dify/               # OpenAPI 与 Chatflow 接线说明
├── docs/               # 架构、评测报告、安全策略、工具说明
├── knowledge-base/     # 产品 / 售后 / 订单 / 退款 知识库
├── prompts/            # System / User Prompt 模板
└── tests/
    ├── golden_set.json
    ├── golden-questions.md
    └── run_eval.py
```

## 安全策略

完整规则见 [docs/safety-policy.md](docs/safety-policy.md)。摘要：

- 过热 / 异味 / 冒烟：立即停用，引导拨打 400-888-3366
- 不代查他人订单，不索要完整身份证与银行卡号
- 不承诺必退款，仅说明政策与审核流程

## 许可证

MIT
