# 订单查询工具（HTTP + 超时重试 + 失败降级）

> 作品集阶段对接自建 Mock OMS；生产可替换为真实 ERP/OMS，契约不变。

## 工具定义

| 字段 | 值 |
|------|-----|
| 名称 | `query_order` |
| 入口 | `GET /api/v1/tools/query_order`（推荐）或直查 `GET /api/v1/orders/{id}` |
| 触发条件 | 用户询问订单状态、物流、发货进度且提供订单号 |
| 超时 | 单次 5s（可配 `ORDER_HTTP_TIMEOUT_SEC`） |
| 重试 | 最多 2 次退避重试（5xx / Timeout / Network） |
| 失败策略 | `degraded=true` + 转人工话术；可选写 `tickets` 表 |

## 入参

```json
{
  "order_id": "PP20260713001234",
  "force_fail": null
}
```

`force_fail` 混沌参数：`timeout` | `500` | `503`，用于演示重试与降级（面试加分项）。

## 成功出参

```json
{
  "ok": true,
  "degraded": false,
  "attempts": 1,
  "data": {
    "order_id": "PP20260713001234",
    "status": "已发货",
    "status_code": "shipped",
    "created_at": "2026-07-13 10:00:00",
    "product": "星眠 Pro 版 SS-200",
    "amount": 499.0,
    "logistics": {
      "company": "顺丰速运",
      "tracking_no": "SF1234567890",
      "last_update": "2026-07-13 18:00:00",
      "detail": "快件已到达【深圳转运中心】"
    }
  }
}
```

## Mock 数据集

| order_id | status |
|----------|--------|
| PP20260713001234 | 已发货 |
| PP20260712005678 | 待发货 |
| PP20260711009999 | 已完成 |

## Dify 接线

见 [dify-http-tool.md](./dify-http-tool.md) 与 [../dify/http-tool-setup.md](../dify/http-tool-setup.md)。OpenAPI：`../dify/openapi-query-order.json`。

## 面试讲解要点

- Agent = LLM + 知识库 + **可失败的工具**
- 知识库答「怎么查」；HTTP 工具答「你的订单到哪了」
- 超时/5xx → 重试 → 仍失败 → **不编造** → Trace + Ticket
- 换 Dify 账号编排层可变；**SQLite 会话 / 日志 / OMS 契约**仍是自有资产
