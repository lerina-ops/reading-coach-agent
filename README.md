# 陪我读书的 Agent

一个用 Python + Streamlit 实现的本地读书教练 MVP。

它不是普通摘要工具，而是帮助你记录阅读、理解章节、追问困惑、复盘思考，并把长期笔记保存到本地。

## 功能

- 新建一本书：书名、作者、阅读目的
- 上传书籍资料：支持 txt、md、pdf，保存为本地资料库
- 记录一次阅读：章节、今日目标、书摘、我的困惑
- 生成陪读反馈：
  - 通俗解释
  - 核心观点
  - 底层逻辑
  - 现实生活例子
  - 对你的两个追问
  - 今日读书笔记
  - 3 个复习问题
- 实时陪读对话：围绕某本书和历史记录继续追问、解释、举例
- 对话模式：像朋友一样聊、讲明白、追问、举例、复盘成笔记
- 快捷追问：一键让 Agent 解释、举例、反问、纠偏、整理笔记
- 保存阅读记录到本地 JSON
- 保存每本书的陪读对话到本地 JSON
- 查看历史阅读记录
- 按书名导出 Markdown 笔记，包含阅读记录和陪读对话
- 使用 `prompts/reading_coach.md` 定义 Agent 人格和工作流程

## 项目结构

```text
.
├── app.py
├── requirements.txt
├── README.md
├── prompts/
│   └── reading_coach.md
└── reading_coach/
    ├── __init__.py
    ├── coach.py
    └── storage.py
```

运行后会自动创建：

```text
data/
├── books.json
├── reading_records.json
├── chat_messages.json
└── book_sources/

exports/
└── xxx_reading_notes.md
```

## 安装依赖

建议先创建虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 运行

```bash
streamlit run app.py
```

浏览器打开终端里显示的地址，一般是：

```text
http://localhost:8501
```

## AI 生成说明

应用支持两种模式：

1. 不填 API Key：使用本地模板生成陪读反馈，适合先体验完整流程。
2. 填写模型 API 配置：调用真实模型生成更自然的陪读反馈和对话。

页面左侧侧边栏支持：

- `API Base URL`：默认 `https://api.openai.com/v1`
- `API Key`：你的模型服务密钥
- `模型名`：例如 `gpt-4.1-mini`

接口使用 OpenAI-compatible 的 `/chat/completions` 格式，因此也可以接入兼容该格式的其他模型服务。

API Key 只在页面运行时使用，不会保存到本地 JSON。

左侧显示“已填写 API Key”只表示配置已填写。请点击“测试模型连接”确认网络、Key、余额、Base URL 和模型名都可用。

也可以用环境变量设置默认值：

```bash
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_API_KEY="你的 API Key"
export OPENAI_MODEL="gpt-4.1-mini"
streamlit run app.py
```

你可以修改 `prompts/reading_coach.md` 来调整 Agent 的人格、输出风格和工作流程。

## 数据保存位置

- 书籍信息：`data/books.json`
- 书籍资料库：`data/book_sources/`
- 阅读记录：`data/reading_records.json`
- 陪读对话：`data/chat_messages.json`
- 导出的 Markdown：`exports/`

这些文件都保存在本地项目目录中。
