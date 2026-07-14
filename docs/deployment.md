# 发布与集成指南

## 1. 发布 Web 应用

1. Dify 工作流页 → **发布** → **发布更新**
2. **发布** → **运行** 或 **在探索中打开**
3. 复制 Web 链接，填入 `README.md` 演示区

## 2. 嵌入网站（可选）

1. **发布** → **嵌入网站**
2. 复制 iframe 代码
3. 保存为 `docs/embed.html`（勿提交含 Secret 的配置）

```html
<!DOCTYPE html>
<html>
<head><title>星眠客服 Demo</title></head>
<body>
  <h1>星眠智能客服</h1>
  <!-- 粘贴 Dify 提供的 iframe -->
</body>
</html>
```

## 3. API 调用（作品集说明用）

**Base URL**：`https://api.dify.ai/v1`

**端点**（Chatflow 一般为）：
```
POST /chat-messages
```

**Headers**：
```
Authorization: Bearer app-你的Dify应用Key
Content-Type: application/json
```

**Body 示例**：
```json
{
  "inputs": {},
  "query": "三个型号有什么区别？",
  "response_mode": "blocking",
  "user": "portfolio-demo-001"
}
```

⚠️ **切勿将 App API Key 提交到 GitHub**

## 4. 演示检查清单

- [ ] 发布成功，链接可访问
- [ ] 开场白和推荐问题显示正常
- [ ] 移动端浏览器可打开（加分项）
- [ ] 录制 2 分钟演示视频

## 5. GitHub Topics 建议

`dify` `rag` `llm` `agent` `customer-service` `chatbot` `portfolio`
