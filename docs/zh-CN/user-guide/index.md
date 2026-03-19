# 用户指南

ReAct Agent 的使用教程和说明。

## 文档列表

| 文档 | 说明 |
|------|------|
| [zh-CN_user_guide.md](zh-CN_user_guide.md) | 完整用户指南：安装、配置、使用方式、API 参考 |


## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/tools` | GET | 获取可用工具列表 |
| `/chat` | POST | 发送消息并获取完整回复 |
| `/chat/stream` | POST | 发送消息并通过 SSE 流式获取回复 |
