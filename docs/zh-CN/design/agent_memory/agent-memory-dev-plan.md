# Agent Memory 开发计划

## 用户故事与边界

### 用户故事 1：agent 可以按主题写入新的长期记忆

- Happy path：模型识别到“请记住”类指令后，调用创建工具，新建一个 Markdown 文件并返回成功摘要。
- Boundary：如果文件已存在，不覆盖，提示改用更新工具。
- Boundary：如果用户内容中包含 YAML 特殊字符，仍能被后端正确序列化，不破坏 Frontmatter。

### 用户故事 2：agent 可以列出已有记忆主题

- Happy path：模型调用列表工具，获得主题摘要列表，用于路由到正确文件。
- Boundary：空目录时返回空数组或空列表提示，而不是报错。
- Boundary：扫描时忽略 `.backup/` 和非 `.md` 文件。

### 用户故事 3：agent 可以读取和更新已有主题

- Happy path：模型先列主题、再读文件、再决定 append 或 rewrite。
- Boundary：`rewrite` 前必须先读当前文件，避免凭空覆盖。
- Boundary：如果文件不存在，更新工具返回明确错误，不隐式创建新文件。

### 用户故事 4：记忆目录总是跟随运行时数据目录

- Happy path：当 `db_path` 指向 `./output/sessions.db` 时，记忆目录为同层的 `./output/agent_memory/`。
- Boundary：`db_path=':memory:'` 时，自动切换到临时目录，测试结束后可清理。

## 前后端调用链

### 新建记忆

```text
用户说“记住我对花生过敏”
	-> LLM 决定调用 create_memory_file
	-> agent_core.tools.agent_memory.register_memory_tools()
	-> AgentMemoryService.create_memory_file(...)
	-> AgentMemoryFileStore 在 data_root/agent_memory/ 下生成 <filename>.md
	-> 后端 safe_dump Frontmatter + 写入正文 + 返回主题摘要
	-> LLM 用工具结果向用户确认已记住
```

### 浏览和读取记忆

```text
用户问“你记得我的饮食偏好吗”
	-> LLM 先调用 list_memory_topics()
	-> AgentMemoryService.list_topics()
	-> 扫描 agent_memory/*.md 并解析 Frontmatter
	-> LLM 选择候选主题后调用 read_memory_file(filename)
	-> AgentMemoryService.read_memory_file(filename)
	-> 返回完整 Markdown 文本供模型引用
```

### 更新记忆

```text
用户说“补充：我现在也不吃海鲜”
	-> LLM 先 read_memory_file(filename)
	-> 决策使用 append 或 rewrite
	-> update_memory_file(filename, mode, ...)
	-> service 获取同文件锁
	-> rewrite 时先写 .backup/<timestamp>_<filename>.md
	-> 写回新正文并刷新 last_updated
	-> 返回更新后的主题摘要
```

关键设计约束：

- 所有文件 I/O 必须在 service / store 层通过 `asyncio.to_thread` 执行
- 工具层只负责参数接收、错误转义和 JSON / 文本输出，不直接处理路径或 YAML
- 目标目录从 `Path(cfg.db_path).parent / "agent_memory"` 推导，不在工具里硬编码绝对路径

## 开发工作项

1. 定义模型与文件协议
	- 新增 Frontmatter 模型、主题摘要模型、更新模式枚举。
	- 约定统一文件扩展名 `.md`，后端负责补全。

2. 新增 agent memory service / provider
	- 参考现有 email provider 模式，提供延迟初始化单例。
	- 统一解析 `db_path` 和 `data_root`，兼容 `:memory:`。

3. 新增文件存储能力
	- 实现 list / read / create / update 四类操作。
	- `rewrite` 自动备份到 `.backup/`。
	- 同文件写入采用锁保护，避免并发覆盖。

4. 新增工具模块并接入自动发现
	- 在 `agent_core.tools` 下新增 `agent_memory.py`。
	- 暴露 `list_memory_topics`、`read_memory_file`、`create_memory_file`、`update_memory_file`。

5. 强化安全与错误处理
	- 文件名规范化、根目录边界校验、备份目录过滤。
	- 错误信息要可供模型自纠，而不是抛裸异常。

6. 补文档与运行约束
	- 用户指南、设计索引、开发计划、测试计划同步维护。
	- 如系统提示需要配合主题拆分规则，后续在实现阶段单独更新提示词。

## 开发完成判定

- 新工具模块能被 `auto_discover_and_register()` 自动注册
- 记忆目录始终落在运行时数据目录下的 `agent_memory/`
- 新建文件时 Frontmatter 由后端生成，且字段完整可解析
- `append` 与 `rewrite` 行为分离明确，`rewrite` 会先备份
- 非法文件名、越界路径、缺失文件都返回可预期错误
- `:memory:` 场景不污染真实磁盘目录
- 后续 focused tests 与完整检查脚本具备可执行验证路径