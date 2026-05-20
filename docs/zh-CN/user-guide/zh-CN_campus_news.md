# Campus News 用户指南

本文档介绍如何通过 Campus News 功能查看校园新闻、搜索通知、查看详情并生成每日摘要。

---

## 1. 功能概览

Campus News 用于聚合校园新闻、活动、机会和通知，并以新闻摘要 Widget 的形式展示在右侧工作区。

| 功能 | 说明 |
|------|------|
| 查看最新新闻 | 获取所有来源中的最新校园新闻 |
| 按日期查看 | 查看某一天的校园新闻 |
| 关键词搜索 | 搜索活动、讲座、招聘、图书馆等相关通知 |
| 查看新闻详情 | 打开新闻卡片查看完整内容 |
| 生成每日摘要 | 基于当前筛选条件生成 daily report |

---

## 2. 新闻来源

当前 Campus News 支持多来源聚合：

| 来源 | 说明 |
|------|------|
| Mock source | 用于本地开发和测试的示例校园新闻 |
| Email source | 从已同步并缓存的邮件中筛选校园新闻类邮件 |

Email source 不会主动连接邮箱，也不会重新拉取邮件。它只读取 Email 功能已经同步到本地缓存/数据库中的邮件，并根据发件人、主题、正文预览和关键词判断邮件是否像校园通知、活动、讲座、职业发展或报名信息。

符合条件的邮件会被转换成统一的新闻格式，用于新闻列表、详情页、digest 和 daily report。

---

## 3. 使用方式

### 3.1 通过对话查询新闻

可以直接向 Agent 提问：

```text
今天有什么校园新闻？
```

```text
帮我搜索 career fair 相关的通知。
```

```text
生成今天的校园新闻摘要。
```

```text
查看最新的校园活动和报名机会。
```

Agent 会根据请求调用 `get_latest_news`、`get_daily_news`、`search_news`、`get_news_detail` 或 `create_news_digest` 等工具。

### 3.2 通过前端 Widget 使用

打开 Campus News 工作区后，可以：

1. 使用日期选择器查看某一天的新闻。
2. 在搜索框输入关键词，例如 `career`、`library`、`seminar`。
3. 使用 Source 下拉框筛选来源，例如 Email、Mock、Official site。
4. 点击新闻卡片进入详情页。
5. 点击 Generate Daily 生成当前筛选条件下的每日新闻报告。

当新闻来自邮件且没有外部链接时，详情页会直接展示邮件正文转换后的内容。

---

## 4. 支持的工具与 API

| 场景 | Agent 工具 / API | 说明 |
|------|------------------|------|
| 查看最新新闻 | `get_latest_news` / `/news/latest` | 返回所有来源的最新新闻 |
| 查看某一天新闻 | `get_daily_news` / `/news?target_date=...` | 按日期过滤新闻 |
| 搜索新闻 | `search_news` / `/news?query=...` | 按关键词搜索新闻 |
| 查看新闻详情 | `get_news_detail` / `/news/{news_id}` | 展示完整内容 |
| 生成新闻摘要 | `create_news_digest` / `/news/digest` | 生成适合工作区展示的新闻摘要 |
| 生成每日报告 | `/news/report` | 基于当前筛选条件生成 AI daily report |

---

## 5. 常见问题

### Q: Campus News 会自动收取新邮件吗？

不会。Campus News 只读取 Email 功能已经同步到本地缓存/数据库中的邮件。需要先通过 Email 功能完成同步，Campus News 才能从这些邮件中筛选新闻类内容。

### Q: 为什么有些邮件没有出现在新闻列表里？

系统会保守筛选新闻类邮件，避免把私人邮件、验证码、账单、登录提醒等内容误认为校园新闻。只有带有校园通知、活动、讲座、职业发展、报名等信号的邮件才会被转换为新闻。

### Q: Mock source 和 Email source 会一起出现在新闻列表里吗？

会。`NewsService` 会聚合当前可用的新闻来源，并按日期排序后返回给工具、API 和前端 Widget。
