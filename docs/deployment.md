# 部署上线方案

## 一、Dify 发布方式

### 方式1：Web App（最快）

1. 在 Dify 中打开你的应用
2. 点击右上角「发布」→「运行 WebApp」
3. 获得一个 WebApp URL，可直接分享或嵌入网站

### 方式2：嵌入式聊天组件

1. 在 Dify 中打开应用 →「API访问」
2. 找到「嵌入式聊天组件」
3. 复制 iframe 代码或 JS SDK 代码
4. 嵌入到你的网站 HTML 中

**iframe 方式：**
```html
<iframe
  src="https://udify.app/chatbot/你的应用ID"
  style="width: 100%; height: 600px; border: none;"
></iframe>
```

**JS SDK 方式（推荐，支持右下角浮窗）：**
```html
<script
  src="https://udify.app/embed.min.js"
  id="你的应用ID"
  defer>
</script>
```

### 方式3：API 调用（最灵活）

适合接入自有 App / 小程序 / 企业系统。

#### 获取 API Key

1. Dify → 你的应用 → API访问
2. 点击「创建密钥」
3. 复制 `app-xxx` 格式的密钥

#### Python 接入示例

```python
import requests

API_KEY = "app-xxx"
BASE_URL = "https://api.dify.ai/v1"

def chat(query, user_id, conversation_id=None):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": {},
        "query": query,
        "response_mode": "blocking",
        "user": user_id,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    resp = requests.post(
        f"{BASE_URL}/chat-messages",
        headers=headers,
        json=payload,
        timeout=30
    )
    data = resp.json()
    return {
        "answer": data.get("answer", ""),
        "conversation_id": data.get("conversation_id", ""),
        "message_id": data.get("message_id", ""),
    }

# 使用
result = chat("SS-200多少钱？", "user-123")
print(result["answer"])

# 多轮对话（传入 conversation_id）
result2 = chat("那SS-300呢？", "user-123", conversation_id=result["conversation_id"])
print(result2["answer"])
```

#### 流式输出（SSE）

```python
import requests
import json

def chat_stream(query, user_id):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": {},
        "query": query,
        "response_mode": "streaming",
        "user": user_id,
    }
    resp = requests.post(
        f"{BASE_URL}/chat-messages",
        headers=headers,
        json=payload,
        stream=True,
        timeout=30
    )
    full_answer = ""
    for line in resp.iter_lines():
        if line:
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data.get("event") == "message":
                    full_answer += data.get("answer", "")
                    print(data.get("answer", ""), end="", flush=True)
    print()
    return full_answer

chat_stream("蓝牙怎么连不上？", "user-123")
```

#### Node.js 接入示例

```javascript
const API_KEY = "app-xxx";
const BASE_URL = "https://api.dify.ai/v1";

async function chat(query, userId, conversationId = null) {
  const payload = {
    inputs: {},
    query,
    response_mode: "blocking",
    user: userId,
  };
  if (conversationId) payload.conversation_id = conversationId;

  const resp = await fetch(`${BASE_URL}/chat-messages`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  return {
    answer: data.answer,
    conversationId: data.conversation_id,
  };
}

// 使用
const result = await chat("7天能退货吗？", "user-123");
console.log(result.answer);
```

---

## 二、微信小程序接入

### 架构

```
微信小程序 → 你的后端服务器 → Dify API
```

> ⚠️ 微信小程序不能直接调用 Dify API（域名白名单限制），需要通过自己的后端中转。

### 后端中转（Python Flask 示例）

```python
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
DIFY_API_KEY = "app-xxx"
DIFY_BASE_URL = "https://api.dify.ai/v1"

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    query = data.get("query", "")
    user_id = data.get("user_id", "anonymous")
    conversation_id = data.get("conversation_id")

    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": {},
        "query": query,
        "response_mode": "blocking",
        "user": user_id,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    resp = requests.post(
        f"{DIFY_BASE_URL}/chat-messages",
        headers=headers,
        json=payload,
        timeout=30
    )
    result = resp.json()
    return jsonify({
        "answer": result.get("answer", ""),
        "conversation_id": result.get("conversation_id", ""),
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

---

## 三、监控与运维

### 1. Dify 内置监控

在 Dify 控制台 →「日志与标注」中可查看：

| 指标 | 说明 |
|------|------|
| 对话数 | 每日/每周/每月对话量 |
| Token 消耗 | 各节点 Token 用量 |
| 响应时间 | 端到端延迟 |
| 用户满意度 | 点赞/踩比例 |
| 错误率 | API 调用失败比例 |

### 2. 自定义监控脚本

保存为 `scripts/health_check.py`，用 cron 每5分钟运行一次：

```python
import requests
import time
import json
from datetime import datetime

API_KEY="app-..._URL = "https://api.dify.ai/v1"
WEBHOOK_URL="https://hooks.feishu.cn/xxx"  # 飞书/钉钉/企微 Webhook

def health_check():
    try:
        start = time.time()
        resp = requests.post(
            f"{API_BASE_URL}/chat-messages",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"inputs": {}, "query": "你好", "response_mode": "blocking", "user": "health-check"},
            timeout=15
        )
        elapsed = time.time() - start
        if resp.status_code == 200 and elapsed < 5:
            return {"status": "OK", "latency": round(elapsed, 2)}
        else:
            return {"status": "WARN", "latency": round(elapsed, 2), "code": resp.status_code}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def send_alert(result):
    if result["status"] != "OK":
        msg = f"SmartSleep-CS Alert: {result}"
        requests.post(WEBHOOK_URL, json={"content": msg}, timeout=5)

if __name__ == "__main__":
    result = health_check()
    print(f"[{datetime.now().isoformat()}] {result}")
    send_alert(result)
```

### 3. 关键监控指标

| 指标 | 告警阈值 | 检查频率 |
|------|----------|----------|
| API 可用性 | 连续3次失败 | 5分钟 |
| 响应时间 | >5秒 | 5分钟 |
| 分类准确率 | <85% | 每日抽检 |
| 检索空结果率 | >20% | 每日 |
| Token 消耗异常 | 日消耗 >2倍均值 | 每日 |
| 用户差评率 | >15% | 每日 |

### 4. 日志分析流程

```
每日 → Dify日志 → 找bad case → 标注正确答案 → 补充知识库 → 优化Prompt
```

**标注方法：**
1. Dify → 日志与标注 → 找到不满意回答
2. 点击「标注」→ 输入正确答案
3. 标注数据可用于后续模型微调

---

## 四、成本估算

### 单次对话成本

| 环节 | Token 估算 | 模型 | 单价(每1K tokens) | 成本 |
|------|-----------|------|-------------------|------|
| 问题分类 | ~200 | GPT-5.5 | $0.00015 | ¥0.001 |
| 知识检索 | ~500 | text-embedding-3-large | $0.00013 | ¥0.0005 |
| LLM回答 | ~800 | GPT-5.4 | $0.005 | ¥0.03 |
| **合计** | ~1500 | - | - | **¥0.03/次** |

### 月度成本估算

| 日对话量 | 月成本(GPT-5.4) | 月成本(DeepSeek-V3) |
|----------|----------------|-------------------|
| 100 | ¥90 | ¥9 |
| 500 | ¥450 | ¥45 |
| 1000 | ¥900 | ¥90 |
| 5000 | ¥4,500 | ¥450 |

> 💡 如需降本，可将 LLM 替换为 DeepSeek-V3 或 Qwen-Plus，成本降低 80-90%

---

## 五、上线 Checklist

- [ ] 知识库已上传并验证检索效果
- [ ] 4个分类分支全部测试通过
- [ ] 对抗测试全部防御成功
- [ ] API Key 已配置
- [ ] 响应时间 <3秒
- [ ] 人工客服兜底联系方式已配置（400-888-3366 / service@starsleep.cn）
- [ ] 监控告警已配置
- [ ] 日志标注流程已建立
- [ ] 成本预算已确认
