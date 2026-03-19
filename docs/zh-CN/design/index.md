# 设计文档

ReAct Agent 核心功能的架构和设计决策。

## 架构概览

本项目采用 **ReAct（Reasoning + Acting）** 架构模式，基于 LangGraph StateGraph 实现循环推理：

```
用户输入 → LLM 推理 → 是否需要工具？ → 工具调用 → 观察结果 → 继续推理 → 最终回答
                           ↓ 否
                        直接回答
```

### 核心设计决策

- **LangGraph StateGraph**：使用有状态图管理推理循环，支持条件分支和流式输出
- **工具注册表模式**：`ToolRegistry` 提供装饰器式注册，解耦工具定义与引擎逻辑
- **HITL 敏感度**：工具分为 `SAFE` 和 `SENSITIVE` 级别，为未来的人工审批做准备
- **SSE 流式输出**：通过 `POST /chat/stream` 实时推送推理步骤，提升用户体验
- **Monorepo 分层**：核心引擎、前端、CLI 解耦，通过 HTTP API 通信

## 文档列表

- [已实现功能模块概览](zh-CN_feature_overview.md) — 所有已实现模块的功能概述，涵盖引擎核心、工具系统、API 层、CLI、Chainlit POC、Vue3 前端
- [Core 核心引擎实现详解](zh-CN_core_implementation.md) — ReactAgent 类架构、LangGraph 状态图、ToolRegistry 工具系统、FastAPI 服务器、配置管理的深入分析
- [CLI 实现详解](zh-CN_cli_implementation.md) — argparse 子命令设计、交互式对话循环、服务器启动的实现细节
- [Chainlit POC 前端实现详解](zh-CN_poc_frontend_implementation.md) — Chainlit 会话管理、流式思维链可视化、工具调用步骤展示的实现细节
- [Vue3 前端实现详解](zh-CN_vue_frontend_implementation.md) — API 客户端层、Pinia 状态管理、ChatView 组件、SSE 解析、Vite 代理配置的实现细节
