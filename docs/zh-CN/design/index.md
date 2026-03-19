# 设计文档

ReAct Agent 核心功能的架构和设计决策。

## 文档列表

*随着项目迭代，设计文档将在此列出。*

## 架构概览

本项目采用 ReAct（Reasoning + Acting）架构模式：

```
用户输入 → LLM 推理 → 工具调用 → 观察结果 → 继续推理 → 最终回答
```

核心基于 LangGraph StateGraph 实现循环推理，支持流式输出（SSE）。
