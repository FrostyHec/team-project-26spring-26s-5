# Agent Memory 设计

## 背景

本功能为 ReAct Agent 新增一套“文件型长期记忆”机制。记忆以 Markdown 文件存储，采用多文件 / 多主题路由，文件头使用 YAML Frontmatter 保存元数据，正文保存可读内容。

本页记录该功能的规划入口，当前约束如下：

- 存储根目录为与主数据库同层的数据目录下的 `agent_memory/`
- 以工具方式暴露给大模型，而不是新增一套独立 UI 流程
- 后端统一负责 YAML 生成、文件名校验、根目录边界校验、备份与并发写保护

## 相关文档

- 开发计划：`agent-memory-dev-plan.md`
- 测试计划：`agent-memory-test-plan.md`
- 用户指南：`../../user-guide/zh-CN_agent_memory.md`
