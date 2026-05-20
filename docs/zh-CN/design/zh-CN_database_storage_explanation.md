# A015: 数据库存储架构解析

## 1. 当前路径模型

运行时可写数据由 `DATA_PATH` 控制。`DB_PATH` 是数据库目录，不是某一个数据库文件；当 `DB_PATH` 留空时，程序默认使用 `DATA_PATH` 作为数据库目录。

```dotenv
DATA_PATH=./output
DB_PATH=
```

以上配置会让运行时数据库写入：

```text
output/
├── sessions.db
├── courses.db
├── course_materials.db
├── email.db
├── deadlines.db
├── logs/
│   └── agent.log
├── llm_settings.yaml
├── pdfs/
└── policy_index/
```

如果使用 `agent-cli serve --env-file /path/to/.env`，相对路径会以该 `.env` 文件所在目录为基准解析，便于打包产物把配置文件放在可编辑目录中。

## 2. 数据库文件职责

项目运行时使用多个 SQLite 文件，文件名固定，目录由 `DB_PATH` 决定：

| 文件名 | 主要用途 | 初始化位置 |
|--------|----------|------------|
| `sessions.db` | 聊天会话、消息、分支版本、用户 profile、alarm 表 | `api/dependencies.py` |
| `courses.db` | 课程 CRUD | `api/dependencies.py` / `course_provider.py` |
| `course_materials.db` | 课程资料元数据 | `api/dependencies.py` / `course_material_provider.py` |
| `email.db` | 邮件缓存与状态 | `api/dependencies.py` / `email_provider.py` |
| `deadlines.db` | deadline CRUD 与 alarm 关联查询 | `api/dependencies.py` / `deadline_provider.py` |

`sessions.db` 仍然是部分子系统共享的 SQLite 文件，但配置层不再区分“主库/副库”。代码统一通过固定文件名在 `DB_PATH` 目录下创建数据库。

## 3. 初始化流程

应用启动时，`AgentConfig.from_env()` 解析：

1. `DATA_PATH`，默认 `./output`
2. `DB_PATH`，留空默认等于 `DATA_PATH`
3. `LOG_FILE`，留空默认 `${DATA_PATH}/logs/agent.log`
4. `LLM_SETTINGS_PATH`，留空默认 `${DATA_PATH}/llm_settings.yaml`

`init_dependencies()` 随后把数据库目录与固定文件名组合：

```python
SessionStore(database_file(config.db_path, "sessions.db"))
CourseStore(database_file(config.db_path, "courses.db"))
CourseMaterialStore(database_file(config.db_path, "course_materials.db"))
EmailStore(database_file(config.db_path, "email.db"))
DeadlineStore(database_file(config.db_path, "deadlines.db"))
```

`database_file(":memory:", "...")` 会继续返回 `":memory:"`，用于测试或临时会话。

## 4. 与其他运行时目录的关系

数据库目录只负责 SQLite 文件。其他可写资产按 `DATA_PATH` 派生：

| 路径 | 默认值 | 用途 |
|------|--------|------|
| `LOG_FILE` | `${DATA_PATH}/logs/agent.log` | 后端日志 |
| `LLM_SETTINGS_PATH` | `${DATA_PATH}/llm_settings.yaml` | LLM provider/settings YAML |
| `POLICY_PDF_DIR` | `${DATA_PATH}/pdfs` | Policy Search 原始 PDF |
| `POLICY_INDEX_DIR` | `${DATA_PATH}/policy_index` | Policy Search 向量索引 |
| Course materials | `${DATA_PATH}/course_materials` | 用户上传的课程资料文件 |
| Agent memory | `${DB_PATH}/agent_memory` | Agent Memory Markdown 文件 |
| Encryption key | `${DATA_PATH}/.encryption_key` | 本地加密密钥 |

## 5. 最佳实践

- 常规开发和打包运行时，推荐只配置 `DATA_PATH`，让 `DB_PATH` 保持为空。
- 只有需要把 SQLite 数据库目录单独放到别处时，才配置 `DB_PATH=/path/to/databases`。
- 测试中可以继续使用 `DB_PATH=:memory:` 或直接构造 `AgentConfig(db_path=":memory:")`。
- 打包产物应把可编辑 `.env` 放在运行时目录，并通过 `--env-file` 启动，确保相对路径稳定。
