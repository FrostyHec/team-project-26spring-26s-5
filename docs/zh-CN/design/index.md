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

*随着项目迭代，以下设计文档将在此列出：*

- 引擎架构设计
- 工具系统设计
- API 接口设计
- 前端状态管理设计
- 安全性与 HITL 设计
