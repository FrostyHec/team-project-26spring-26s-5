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

- [已实现功能模块概览](zh-CN_feature_overview.md) — 所有已实现模块的功能概述，涵盖引擎核心、工具系统、API 层、CLI、Vue3 前端
- [Core 核心引擎实现详解](zh-CN_core_implementation.md) — ReactAgent 类架构、LangGraph 状态图、ToolRegistry 工具系统、FastAPI 服务器、配置管理的深入分析
- [CLI 实现详解](zh-CN_cli_implementation.md) — argparse 子命令设计、交互式对话循环、服务器启动的实现细节
- [Vue3 前端实现详解](zh-CN_vue_frontend_implementation.md) — API 客户端层、Pinia 状态管理、ChatView 组件、SSE 解析、Vite 代理配置的实现细节
- [Sessions 与对话面板设计](sessions/index.md) — discussion panel 增强计划，包括会话树、中断恢复、debug 与多 provider
- [Think 链路分离计划](think_chain/index.md) — 分析 `think` 如何泄漏到最终回答，并规划后端分流、持久化清洗与回归测试
- [Agent Memory 设计](agent_memory/index.md) — 多文件 Wiki 路由记忆规划，包含 Markdown Frontmatter 存储、工具接口与测试计划
- [截止日期管理实现详解](zh-CN_deadline_management.md) — 截止日期功能的后端与前端实现细节
- [Settings 设置功能实现详解](zh-CN_settings_extension.md) — 用户凭据存储、AES 加密、REST API 设计与前端设置面板架构
- [Vue I18n 国际化实现详解](zh-CN_i18n_implementation.md) — 中英文双语支持的架构设计、语言包结构、组件接入方式与语言切换机制
- [Deadline 管理设计](zh-CN_deadline_management.md) — 三层架构参考实现：Controller–Service–Store 分层、SQLModel ORM、类型安全校验
- [CRUD 开发指南](zh-CN_crud_development_guide.md) — SQLModel 异步 ORM 标准模式、三层校验分工、常见陷阱和检查清单
- [Email 功能实现详解](zh-CN_email_implementation.md) — IMAP/SMTP 邮件功能全栈实现：数据模型、EmailStore 保留策略、EmailClient 线程模型、懒加载正文、附件两阶段下载、`\Seen` 同步可靠性修复、Vue3 前端
