# Dify 接入：HTTP 订单工具（超时 / 重试 / 降级）

## 目标

把 workflow 里的 Code Mock 换成**真实 HTTP 工具闭环**：

```
用户问订单 → 提取 order_id → HTTP GET tools/query_order
  ├─ ok=true  → LLM 复述 data（禁止编造字段）
  └─ degraded=true → 固定话术转人工（不编造物流）
```

## 1. 启动自有后端

见 `backend/README.md`。Dify Cloud 需公网地址（ngrok / 云主机），并把 `.env` 里 `PUBLIC_BASE_URL` 改成公网 URL。

## 2. 导入 OpenAPI 工具（推荐）

1. Dify → 工具 → 自定义工具 → 从 OpenAPI 导入  
2. 选择 `dify/openapi-query-order.json`  
3. 把 servers.url 改成你的公网 Base URL  
4. 在 Agent / LLM 节点启用工具 `query_order`

## 3. Chatflow HTTP Request 节点（无自定义工具时）

| 项 | 值 |
|----|-----|
| Method | GET |
| URL | `https://YOUR_HOST/api/v1/tools/query_order?order_id={{#sys.query#}}` 或上游 Code 抽出的 order_id |
| Timeout | 8000 ms |
| 失败分支 | 走兜底 / 转人工回复 |

建议上游加一个 Code 节点只做正则抽单号：`PP\d{14}`。抽不到则问用户要订单号。

## 4. 提示词约束（贴进 LLM）

```
订单实时状态必须来自工具 query_order 返回的 JSON。
若 ok=false 或 degraded=true：使用 assistant_hint，禁止编造物流公司/运单号/站点。
若 order_not_found：请用户核对订单号或转人工。
```

## 5. 面试可演示的三条证据

1. `GET /api/v1/orders/PP20260713001234` → 200 JSON  
2. `GET /api/v1/tools/query_order?order_id=...&force_fail=500` → attempts≥2 且 degraded  
3. `GET /api/v1/conversations/{id}/traces` → 出现 `tool.query_order` span
