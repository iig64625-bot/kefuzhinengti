# 🌙 星眠 SmartSleep — 专属智能客服

基于 [Dify](https://dify.ai/) 平台构建的 RAG 智能客服工作流，为「星眠 SmartSleep 智能助眠枕」提供多分支自动问答服务。

## 🏗️ 工作流架构

```
用户提问 → 问题分类器 → 4条分支并行处理
                          ├─ 产品信息 → 知识检索1 → LLM1 → 回复
                          ├─ 使用/售后 → 知识检索2 → LLM2 → 回复
                          ├─ 订单查询 → 知识检索3 → LLM3 → 回复
                          └─ 退款问题 → 知识检索4 → LLM4 → 回复
```

### 核心节点

| 节点 | 类型 | 说明 |
|------|------|------|
| 问题分类器 | Question Classifier | 将用户问题自动分为4类，使用 GPT-5.5 |
| 知识检索 1-4 | Knowledge Retrieval | 各分支检索对应知识库（混合检索：向量0.7 + 关键词0.3） |
| LLM 1-4 | LLM | 各分支独立Prompt，使用 GPT-5.4 |
| 直接回复 1-4 | Answer | 输出对应LLM的回答 |

### 分类体系

| 分类 | 覆盖范围 |
|------|----------|
| **产品信息** | 产品介绍、功能说明、型号区别(SS-100/200/300)、价格、促销、规格参数、购买渠道 |
| **产品使用/售后** | 首次使用、App绑定、蓝牙连接、功能操作、清洁保养、故障排查、保修维修 |
| **订单查询** | 订单状态、物流跟踪、修改地址、发票申请、支付异常 |
| **退款问题** | 退款/退货政策、申请流程、到账时间、进度查询、退货寄回 |

## 📂 项目结构

```
SmartSleep-CS/
├── dify-workflow.yml          # Dify 工作流 DSL（可直接导入 Dify）
├── docs/
│   ├── workflow-architecture.md  # 工作流详细架构说明
│   └── deployment.md          # 部署上线方案（API/嵌入/小程序/监控/成本）
├── tests/
│   ├── test-cases.md          # 测试用例矩阵（52用例+12对抗测试）
│   ├── test_e2e.py            # 自动化端到端测试脚本
│   └── .env.example           # API Key 配置模板
├── knowledge-base/            # 知识库文档（需自行上传至 Dify）
│   ├── product-info/          # 产品信息类文档
│   ├── usage-after-sales/     # 使用/售后类文档
│   ├── order-tracking/        # 订单查询类文档
│   └── refund-policy/         # 退款政策类文档
├── README.md
└── .gitignore
```

## 🚀 快速开始

### 1. 导入工作流

1. 登录 [Dify Cloud](https://cloud.dify.ai/) 或自部署的 Dify 实例
2. 点击「创建应用」→「导入 DSL」
3. 上传 `dify-workflow.yml` 文件
4. 工作流将自动还原所有节点和连接

### 2. 配置知识库

工作流引用了 4 个知识库，导入后需要重新关联：

| 知识库节点 | 建议知识库名称 | 文档来源 |
|------------|---------------|----------|
| 知识检索 1 | 产品信息库 | `knowledge-base/product-info/` |
| 知识检索 2 | 使用售后库 | `knowledge-base/usage-after-sales/` |
| 知识检索 3 | 订单查询库 | `knowledge-base/order-tracking/` |
| 知识检索 4 | 退款政策库 | `knowledge-base/refund-policy/` |

### 3. 配置模型

工作流使用以下模型，需确保 Dify 已配置对应 API Key：

- **问题分类器**：`gpt-5.5`（OpenAI）
- **LLM 1-4**：`gpt-5.4`（OpenAI）
- **Embedding**：`text-embedding-3-large`（OpenAI）

> 💡 可根据实际需求替换为其他模型（如 DeepSeek、Qwen 等），在 Dify 节点设置中修改即可。

## 📋 Prompt 设计要点

每个分支的 System Prompt 都遵循以下原则：

1. **角色限定**：明确客服身份，不替代医疗建议
2. **知识库约束**：仅基于检索结果回答，不编造信息
3. **边界清晰**：各分支只处理自己领域的问题，跨域引导至对应分支
4. **安全兜底**：涉及安全隐患（过热、异味、冒烟）立即提醒停止使用并联系人工客服
5. **情绪处理**：退款分支特别设计了情绪安抚策略

## 📞 人工客服兜底

当知识库无法覆盖时，统一引导至：
- **电话**：400-888-3366
- **邮箱**：service@starsleep.cn

## 📄 License

MIT

---

## 🧪 测试验证

详见 [tests/test-cases.md](tests/test-cases.md)，包含：
- 52个常规测试用例（4分类 + 边界异常）
- 12个对抗测试用例（越狱/注入/跨域/隐私窃取）

**快速运行自动化测试：**
```bash
cd tests
cp .env.example .env  # 填入你的 Dify API Key
pip install requests python-dotenv
python test_e2e.py              # 全量测试
python test_e2e.py --quick      # 只跑P0
python test_e2e.py --adversarial # 含对抗测试
python test_e2e.py --json       # 输出JSON报告
```

## 🚀 部署上线

详见 [docs/deployment.md](docs/deployment.md)，包含：
- 3种发布方式（WebApp / 嵌入式 / API调用）
- Python & Node.js 接入代码
- 微信小程序中转方案
- 监控告警配置
- 成本估算（¥0.03/次 → DeepSeek可降至¥0.003/次）
- 上线 Checklist
