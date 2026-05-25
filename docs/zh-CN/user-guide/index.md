# 用户指南

SUSTech Campus Assistant 的使用教程和说明。

## 文档列表

| 文档 | 说明 |
|------|------|
| [用户指南](zh-CN_user_guide.md) | 安装、配置、使用方式、API 参考 |
| [Policy Search](zh-CN_policy_search.md) | 校园政策搜索：数据源、使用方法、测试问题、添加 PDF 流程 |
| [Campus News](zh-CN_campus_news.md) | 校园新闻搜索、每日摘要、邮件来源新闻 |
| [Course Recommendation](zh-CN_course_recommendation.md) | 课程推荐、课程详情、课程对比 |
| [Deadline Management](zh-CN_deadline_management.md) | 截止日期管理与提醒 |
| [Agent Memory](zh-CN_agent_memory.md) | 长期记忆的主题化 Markdown 存储与更新规则 |
| [Discussion Panel](zh-CN_discussion_panel_upgrade.md) | 对话面板增强：中断、分支、debug、多 API 源 |

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/tools` | GET | 获取可用工具列表 |
| `/skills` | GET | 获取可用 skill 列表 |
| `/chat` | POST | 发送消息并获取完整回复 |
| `/chat/stream` | POST | 发送消息并通过 SSE 流式获取回复 |
