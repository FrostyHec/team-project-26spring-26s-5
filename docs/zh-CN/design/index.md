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

### 架构与总览

- [功能模块概览](zh-CN_feature_overview.md) — 引擎核心、工具系统、API 层、CLI、Vue3 前端
- [Core 核心引擎](zh-CN_core_implementation.md) — ReactAgent、LangGraph 状态图、ToolRegistry、FastAPI、配置管理
- [CLI 实现](zh-CN_cli_implementation.md) — argparse 子命令、交互式对话、服务器启动
- [Vue3 前端](zh-CN_vue_frontend_implementation.md) — API 客户端、Pinia 状态管理、SSE 解析、Vite 代理

### 功能模块

- [Policy Search (RAG)](zh-CN_policy_search_implementation.md) — PDF 摄取、Embedding、FAISS 索引、检索、来源引用
- [Deadline Management](deadline_management/zh-CN_deadline_management.md) — 截止日期功能的后端与前端实现
- [Email](zh-CN_email_implementation.md) — IMAP/SMTP 全栈实现、懒加载正文、附件下载
- [Sessions 与对话面板](sessions/index.md) — 会话树、中断恢复、debug 与多 provider
- [Agent Memory](agent_memory/index.md) — 多文件 Wiki 路由记忆、Markdown Frontmatter 存储
- [Think 链路分离](think_chain/index.md) — think 泄漏分析、后端分流与清洗
- [Settings](zh-CN_settings_extension.md) — 用户凭据、AES 加密、REST API、前端设置面板
- [I18n 国际化](zh-CN_i18n_implementation.md) — 中英文双语、语言包结构、语言切换

### 开发参考

- [CRUD 开发指南](zh-CN_crud_development_guide.md) — SQLModel 异步 ORM 标准模式、三层校验
- [SQLModel 陷阱](zh-CN_sqlmodel_pitfalls.md) — 常见问题与解决方案
- [数据库存储说明](zh-CN_database_storage_explanation.md) — 存储架构与设计决策
- [课程存储实现](zh-CN_course_storage_implementation.md) — 课程数据持久化
- [CI/CD 实践指南](zh-CN_ci_cd_description.md) — GitHub Actions 工作流设计、测试覆盖率分析、自动化部署策略、常见问题和最佳实践
