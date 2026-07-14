# Dify ↔ 后端 HTTP 工具接线（真工具闭环）

目标：订单查询走 **HTTP**，失败走 **超时重试 + 明确降级转人工**，不在对话里编造物流。

## 1. 启动自有后端

```bash
cd starsleep-agent/backend
.venv\Scripts\activate   # Windows
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

本地预览可用 ngrok / Cloudflare Tunnel 暴露公网地址，写入 `.env`：

```
PUBLIC_BASE_URL=https://xxxx.ngrok-free.app
```

## 2. Chatflow 改法（替换 Code Mock）

订单分流分支改为：

```
问题分类器(订单物流)
  → HTTP 请求 GET /api/v1/tools/query_order?order_id={{订单号}}
  → IF 节点：body.ok == true
       ├─ true  → LLM 用返回字段生成话术 → 直接回复
       └─ false → 固定回复（降级转人工）→ 直接回复
```

### HTTP 节点参数

| 项 | 值 |
|----|-----|
| Method | `GET` |
| URL | `{{PUBLIC_BASE_URL}}/api/v1/tools/query_order` |
| Query | `order_id` = 抽取的订单号；可选 `force_fail=500` 演示降级 |
| Timeout | `8` 秒（后端单次超时默认 5s，且最多重试 2 次） |

成功响应示例：

```json
{
  "ok": true,
  "degraded": false,
  "attempts": 1,
  "data": {
    "order_id": "PP20260713001234",
    "status": "已发货",
    "status_code": "shipped",
    "product": "星眠 Pro 版 SS-200",
    "amount": 499.0,
    "logistics": { "company": "顺丰速运", "tracking_no": "SF1234567890", "detail": "..." }
  }
}
```

失败 / 降级：

```json
{ "ok": false, "degraded": true, "attempts": 3, "error": "http_500", "user_message": "..." }
```

`degraded=true` 时：**禁止**让模型编造运单号；用固定话术转人工，并可调用后端 `POST /api/v1/tickets`。

## 3. OpenAPI 自定义工具（Agent 模式）

导入：`dify/openapi-query-order.json`

System Prompt 补充：

> 用户给出 PP 订单号查状态时必须调用 `query_order`；若工具返回 `degraded` 或 `ok=false`，说明暂时查不到，转人工，勿臆造物流。

## 4. 面试可演示脚本

1. 正常：`查订单 PP20260713001234` → 返回「已发货」+ 顺丰单号  
2. 不存在：`PP00000000000000` → `order_not_found` 降级  
3. 混沌：`force_fail=500` → attempts=3 → `degraded=true` → 自动 ticket  

本地一键：

```bash
curl "http://127.0.0.1:8000/api/v1/tools/query_order?order_id=PP20260713001234&force_fail=500"
```
