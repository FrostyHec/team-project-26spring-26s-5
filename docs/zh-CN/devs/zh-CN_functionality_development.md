# 功能开发指南（AI Agent 辅助文档）

本文档为 AI Agent（或开发者）提供**引入新功能模块**时的参考索引。
通过下方链接按需展开阅读对应文档，快速了解项目约定与架构。

---

## 1. Python 后端开发

### 项目结构&规范（必读）

| 文档 | 说明 |
|------|------|
| [项目结构](zh-CN_project_structure.md) | Monorepo 目录树、三大 package（core / cli / gui）的组织方式与依赖关系 |
| [Python 代码规范](zh-CN_code_conventions_python.md) | 格式化（Ruff）、类型标注（Pyright strict）、枚举替代 magic string、SQLModel 模型规范 |


### 可选阅读（根据功能相关性选择阅读）：
| 文档 | 说明 |
|------|------|
| [Core 核心引擎实现](../design/zh-CN_core_implementation.md) | ReactAgent 架构、LangGraph 状态图、ToolRegistry 工具系统、FastAPI 服务器 |
| [CRUD 开发指南](../design/zh-CN_crud_development_guide.md) | Controller–Service–Store 三层架构标准模式、SQLModel 异步 ORM、类型安全校验规范与检查清单 |
| [Deadline 管理设计](../design/zh-CN_deadline_management.md) | 三层架构的参考实现：数据模型、Store / Service / Controller 各层职责、REST API、工具函数 |

## 2. Vue 前端开发（前端必读）

| 文档 | 说明 |
|------|------|
| [Vue3 前端实现](../design/zh-CN_vue_frontend_implementation.md) | API 客户端层、Pinia 状态管理、ChatView 组件、SSE 解析、Vite 代理配置 |
| [Vue / TypeScript 代码规范](zh-CN_code_conventions_vue.md) | Prettier 格式化、组件命名、i18n 国际化、Pinia Store 模式、API 分层 |
| [提交规范](zh-CN_commit_conventions.md) | Conventional Commits 格式、scope 列表（`gui` scope 用于前端改动） |

## 3. 通用参考

| 文档 | 说明 |
|------|------|
| [已实现功能概览](../design/zh-CN_feature_overview.md) | 所有已实现模块一览：引擎核心、工具系统、API 层、CLI、Vue3 前端 |
| [开发者完整指南](zh-CN_developers_guideline.md) | 环境搭建、包管理器（uv / pnpm）、开发服务器启动、CI 流程 |
| [并行开发指南](zh-CN_parallel_dev_guide.md) | 多功能模块并行开发时的分支策略与协作流程 |
| [分发与部署](zh-CN_distribution.md) | 构建产物、打包流程、部署方式 |
| [综合技术参考](zh-CN_agent.md) | 技术栈概览、整体架构图、各层关键实现 |

---

## 4. 硬性要求

> **以下要求在每次功能开发完成后必须逐条满足。**

### 4.1 CI 检查必须通过

功能开发完成后，**必须**运行完整检查脚本并确保全部通过：

```bash
bash scripts/check.sh --check-only
```

该脚本涵盖：格式化检查（Ruff / Prettier）、Lint（Ruff / ESLint）、
类型检查（Pyright / vue-tsc）、全部单元测试（pytest / vitest）。

### 4.2 文档同步更新

所有改动**必须**同步更新 `docs/` 中涉及的相关文档：

1. 阅读 [设计文档索引](../design/index.md) 和 [开发指南索引](index.md) 判断哪些文档受影响
2. 对受影响的文档进行修改，确保描述与当前实现一致
3. 若新增了独立功能模块，在对应 `index.md` 中添加文档链接
