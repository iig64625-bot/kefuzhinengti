# StarSleep CS Backend

Own backend assets for the portfolio Agent (not only Dify orchestration).

## What you get

| Capability | Endpoint / Artifact |
|------------|---------------------|
| Chat + session | `POST /api/v1/chat` → SQLite `conversations` / `messages` |
| Trace | `GET /api/v1/conversations/{id}/traces` |
| Access logs | `GET /api/v1/logs/recent` |
| HITL ticket | `POST /api/v1/tickets` |
| Mock OMS | `GET /api/v1/orders/{order_id}` |
| Tool facade (retry+degrade) | `GET /api/v1/tools/query_order?order_id=` |

## Quick start

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/docs

### Demo chat with real order tool

```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"帮我查订单 PP20260713001234 物流\"}"
```

### Chaos: force OMS 500 → retry → degrade

```bash
curl "http://127.0.0.1:8000/api/v1/tools/query_order?order_id=PP20260713001234&force_fail=500"
```

## Dify HTTP tool

1. Expose this API (local: [ngrok](https://ngrok.com) / cloud deploy)
2. Set `PUBLIC_BASE_URL` to the public URL
3. In Dify HTTP Request node:
   - Method: `GET`
   - URL: `{{PUBLIC}}/api/v1/tools/query_order?order_id={{order_id}}`
   - Timeout: 8s
4. On `degraded=true` → fixed reply / 转人工 (never invent logistics)

OpenAPI import schema: `../dify/openapi-query-order.json`

## Optional Dify proxy

Set `DIFY_API_KEY` and call chat with `"use_dify": true`. On Dify failure the gateway falls back to local RAG.
