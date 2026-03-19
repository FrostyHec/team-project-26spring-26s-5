# 用户指南

ReAct Agent 的使用教程和说明。

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repo-url>
cd team-project-26spring-26s-5

# 安装所有依赖
task init
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env` 并填入你的 OpenAI API Key：

```bash
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY
```

### 3. 启动服务

**CLI 交互模式：**
```bash
task dev:server
# 在另一个终端运行 CLI chat
cd packages/cli && uv run agent-cli chat
```

**Chainlit POC 界面：**
```bash
task dev:poc
# 在浏览器打开 http://localhost:8001
```

**Vue 前端：**
```bash
# 先启动后端
task dev:server
# 再启动前端
task dev:gui
# 在浏览器打开 http://localhost:5173
```

## 内置工具

当前 Agent 内置以下计算工具（POC 演示用途）：

| 工具 | 说明 | 示例 |
|------|------|------|
| add | 加法 | "请计算 3 + 5" |
| subtract | 减法 | "7 减去 2 等于多少" |
| multiply | 乘法 | "4 乘以 6" |
| divide | 除法 | "10 除以 3" |

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/tools` | GET | 获取可用工具列表 |
| `/chat` | POST | 发送消息并获取完整回复 |
| `/chat/stream` | POST | 发送消息并通过 SSE 流式获取回复 |
