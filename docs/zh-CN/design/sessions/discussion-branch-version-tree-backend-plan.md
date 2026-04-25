# Discussion Branch Version Tree — Backend Detail Plan

## 1. 当前代码现实与改造边界

当前后端还没有“树”。真实实现入口是：

- `packages/core/src/agent_core/persistence/session_store.py` 仍只有 `SessionTable + MessageTable`，消息按 `ordinal` 线性持久化。
- `packages/core/src/agent_core/models/session.py` 中 `SessionDetail` 仍然是 `session + messages[]`。
- `packages/core/src/agent_core/api/routes/sessions.py` 的 `GET /sessions/{id}` 直接返回这个线性 `SessionDetail`。
- `packages/core/src/agent_core/engine/agent.py` 在 `chat()` / `stream()` 中通过 `_load_history()` 与 `_persist_messages()` 直接读写线性消息列表。

所以后端细化方案不能只是在现有 `messages` 表上补几个字段了事，否则：

- `chat/stream` 仍会按线性 history 回放上下文；
- `GET /sessions/{id}` 仍没有 `visible_path` 和 `version_groups`；
- `retry / edit / select-version` 只能在前端伪造，后端没有统一真相源。

本轮既然已确认**不要求前向兼容**，建议后端采用“保留 `SessionTable`，但用新树表替换 `MessageTable` 作为对话真相源”的方案，而不是继续在线性消息模型上打补丁。

## 2. 数据库存储方案

### 2.1 保留与新增的表

建议继续复用同一个 `sessions.db`，不要再拆新的 sqlite 文件。原因很直接：

- 当前依赖注入、测试夹具、关闭清理逻辑都已经围绕同一个 session DB 展开。
- branch/version tree 和 session preference 强相关，放同库最简单。
- 本轮允许清库重建，不需要为了迁移方便把新旧结构隔离到两个 DB。

建议表结构如下：

### `sessions`

- 保留现有 `id/title/created_at/updated_at/is_active/selected_provider_id/fallback_mode/pending_state`。
- 新增 `current_leaf_node_id`，表示当前 session 的主显示叶子节点。

### `chat_nodes`

- `id`: uuid
- `session_id`: fk -> sessions.id
- `parent_id`: fk -> chat_nodes.id，可空，root user 为 null
- `role`: user / assistant / tool / system
- `content`: 文本内容
- `status`: completed / interrupted / failed / streaming
- `version_group_id`: 同一语义槽位的版本组 id
- `version_index`: 同组递增版本号
- `source_kind`: initial / retry / user_edit / assistant_edit / fallback
- `source_node_id`: 从哪个旧节点派生
- `created_at`
- `updated_at`
- `response_to_node_id`: 可选，表示 assistant 是响应哪个 user；便于 retry / query

索引建议：

- `(session_id, parent_id, created_at)` 用于取子节点
- `(session_id, version_group_id, version_index)` 用于渲染版本 tabs
- `(session_id, source_node_id)` 用于 debug / 派生链查询

### `chat_version_selections`

这张表只存“一个版本组当前选中了哪个版本”：

- `session_id`
- `version_group_id`
- `selected_node_id`
- `updated_at`

唯一键：`(session_id, version_group_id)`

### `chat_node_bookmarks`

这张表只存“当用户回到某个 node 继续往下看时，上次停在哪个 leaf”：

- `session_id`
- `node_id`
- `selected_leaf_id`
- `updated_at`

唯一键：`(session_id, node_id)`

这样“组选中状态”和“节点末梢书签”就不会互相覆盖：

- `chat_version_selections` 回答“这个 tabs 当前高亮哪一个版本”
- `chat_node_bookmarks` 回答“如果切回这个 node，应优先恢复到哪个 descendant leaf”

这才是正确的拆法。后端不需要每生成一条新消息就更新所有 node 的书签；只需要在“离开当前版本”时给当前 node 写一次 bookmark 即可。

## 3. Store / Service 分层建议

### 3.1 不建议直接把所有树逻辑塞回 `SessionStore`

`SessionStore` 现在承担的是：

- session CRUD
- 线性 message CRUD
- partial/interrupted persistence

如果把树节点创建、版本组切换、路径投影、branch preference 统统直接塞进去，这个类会失控。

更合理的做法是：

- 保留 `SessionStore` 负责 `sessions` 表基础 CRUD。
- 新增 `ConversationTreeStore` 负责 `chat_nodes`、`chat_version_selections` 与 `chat_node_bookmarks`。
- 新增 `ConversationTreeService` 负责高层操作：`retry_assistant`、`edit_user`、`edit_assistant`、`select_version`、`build_session_detail`。

建议依赖关系：

```text
FastAPI routes
	-> ConversationTreeService
			 -> SessionStore
			 -> ConversationTreeStore
```

这样改造 `chat/stream` 时也更清晰：agent 负责生成消息，tree service 负责把结果挂到正确节点上。

### 3.2 实例化与依赖注入

当前 `init_dependencies()` 已经创建了 `_store = SessionStore(_config.db_path)` 并初始化。这里建议改成：

```text
_store = SessionStore(db_path)
await _store.initialize()

_tree_store = ConversationTreeStore(db_path)
await _tree_store.initialize()

_conversation_tree_service = ConversationTreeService(_store, _tree_store)
```

注意点：

- `ConversationTreeStore` 和 `SessionStore` 可以共用同一个 `db_path`，但各自维护自己的 async engine/session 模式即可，不必强行共享同一个 `AsyncSession` 对象。
- 如果你后面想继续精简，也可以让 `ConversationTreeStore` 直接接收 `SessionStore.db` 这类 engine；但第一版不建议耦这么紧。
- `shutdown_dependencies()` 里要同步 close tree store，并重置对应 singleton，避免测试污染。

## 4. 接口设计与后端职责边界

### 4.1 读取接口

建议把 `GET /sessions/{id}` 升级成新的 read model，而不是新增第二个“树详情接口”。因为前端 chat 主入口本来就依赖它。

建议返回：

```json
{
	"session": { "id": "...", "title": "...", "current_leaf_node_id": "..." },
	"nodes": [...],
	"visible_path": ["node-a", "node-b", "node-c"],
	"version_groups": [
		{
			"version_group_id": "vg-1",
			"node_ids": ["n1", "n2"],
			"selected_node_id": "n2",
			"position_in_path": 3
		}
	]
}
```

后端职责是：

- 读取 `sessions.current_leaf_node_id`
- 从该 leaf 一路回溯到 root，得到 `visible_path`
- 找出 path 上每个 node 对应的 `version_group_id`
- 把每个版本组的 siblings 按 `version_index` 带给前端

前端不负责：

- 从全量树猜当前展示链
- 自己决定切旧版本时该显示哪个 descendant leaf

### 4.2 变更接口

建议新增这些接口：

- `POST /sessions/{session_id}/nodes/{assistant_node_id}/retry`
- `PATCH /sessions/{session_id}/nodes/{user_node_id}/edit`
- `PATCH /sessions/{session_id}/nodes/{assistant_node_id}/edit`
- `PATCH /sessions/{session_id}/version-groups/{version_group_id}/select`

所有 mutation 都返回完整 session detail snapshot，而不是只返回“新节点 id”。这是必须的，因为：

- 切换版本会影响整条 `visible_path`
- edit / retry 之后当前叶子、版本组高亮、消息投影都会变化
- 前端如果自己 patch，会再次引入双真相源

## 5. 树写入与读取算法

### 5.1 懒写 bookmark，而不是懒写组选中状态

你担心的点是正确的：如果每生成一个新叶子，都沿祖先链更新 bookmark，成本和复杂度都会放大。

第一版建议使用懒写策略：

- 用户一直顺着当前选中的版本往下聊时，只更新 `sessions.current_leaf_node_id`
- 只有当用户触发 `select-version` 离开当前 node 时，才把“当前 node -> 当前 leaf”写入 `chat_node_bookmarks`
- 当前版本组高亮则单独写入 `chat_version_selections`

这样写的好处：

- 流式输出阶段不需要频繁写 bookmark
- 版本切换语义集中在一个 API 内，便于测试
- 刷新恢复依然可用，因为当前主线直接由 `current_leaf_node_id` 决定

### 5.2 `select-version` 的后端算法

建议顺序：

```text
1. 读取当前 session.current_leaf_node_id
2. 找到当前 visible_path 上属于该 version_group 的当前 node
3. 将这个当前 node 对应的当前 leaf 写入 chat_node_bookmarks
4. 将目标 node_id 写入 chat_version_selections.selected_node_id
5. 解析目标 node_id 的默认 descendant leaf：
	 - 若 chat_node_bookmarks 中已有 selected_leaf_id，优先使用
	 - 否则取该 node 子树中的最新 leaf
6. 更新 sessions.current_leaf_node_id = resolved_leaf_id
7. 返回完整 session detail snapshot
```

### 5.3 `chat/stream` 如何挂树

当前 `ReactAgent.stream()` 是线性模型：

- load history
- append new human message
- graph 执行
- persist new messages

树化后建议不要让 agent 直接知道树结构细节，而是：

- route 或 service 在开流前先决定“本次 user message 要挂在哪个 parent leaf 下”
- tree service 创建 user node，并把它设为当前分支的 active continuation
- agent 只拿该 branch 的 linearized visible history 去推理
- 流结束后 tree service 再创建 assistant node，并更新 `current_leaf_node_id`

也就是说，**线性 history 只是推理输入视图，不再是持久化真相源**。

这点很重要：后端可以继续给 LangGraph 喂一串线性 messages，但数据库里保存的是 tree nodes。

## 6. 关键接口逐个细化

### 6.1 `GET /sessions/{session_id}`

这个接口是整个前端版本树的根。不要再让前端先拿线性 messages，再自己推版本组。

建议 response model：

```json
{
	"session": {
		"id": "session-1",
		"title": "...",
		"selected_provider_id": "provider-a",
		"fallback_mode": "auto",
		"current_leaf_node_id": "node-8"
	},
	"nodes": [
		{
			"id": "node-1",
			"parent_id": null,
			"role": "user",
			"content": "hello",
			"status": "completed",
			"version_group_id": "vg-user-1",
			"version_index": 0,
			"source_kind": "initial",
			"source_node_id": null
		}
	],
	"visible_path": ["node-1", "node-3", "node-8"],
	"version_groups": [
		{
			"version_group_id": "vg-assistant-3",
			"node_ids": ["node-3", "node-6"],
			"selected_node_id": "node-6",
			"position_in_path": 1
		}
	]
}
```

后端实现步骤：

```text
1. 读 session row
2. 取 current_leaf_node_id；若为空则返回空 nodes/empty path
3. 从 leaf 一路 parent_id 回溯到 root，得到 visible_path
4. 一次性查询 session_id 下所有 nodes 或 visible_path 所需 nodes + path 版本组 siblings
5. 对 visible_path 上每个 node 按 version_group_id 聚合 siblings
6. 组装 version_groups，selected_node_id 取 path 中当前节点
7. 返回完整 snapshot
```

错误语义：

- session 不存在 -> 404
- current_leaf_node_id 指向坏数据 -> 500，并记录结构损坏日志；第一版不做静默修复

### 6.2 `PATCH /sessions/{session_id}/version-groups/{version_group_id}/select`

request body 建议：

```json
{
	"node_id": "node-6"
}
```

response：直接返回完整 session detail snapshot。

这个接口的职责不是“改个高亮”，而是正式切换当前显示路径。

后端实现步骤：

```text
1. 校验 session 存在
2. 校验 node_id 属于该 session，且 node.version_group_id == path param
3. 读取旧 current_leaf_node_id，对当前正在离开的那个版本组做一次懒写存档：
	 - 若旧 visible_path 上存在相同 version_group_id 的 current node
	 - 则 upsert chat_node_bookmarks(session_id, node_id=current node,
		 selected_leaf_id=old current leaf)
4. 为目标 version_group_id upsert chat_version_selections.selected_node_id=node_id
5. 解析 node_id 的默认 descendant leaf：
	 - 优先查 chat_node_bookmarks.selected_leaf_id
	 - 查不到则 DFS / 递归 SQL 找该 node 子树最新 leaf
6. 更新 sessions.current_leaf_node_id = resolved leaf
7. 调 build_session_detail() 返回完整 snapshot
```

错误语义：

- node 不属于该 session -> 404 或 400，建议 404
- node 不属于该 version_group -> 400
- 目标 node 不是可见树中的合法版本候选 -> 400

### 6.3 `POST /sessions/{session_id}/nodes/{assistant_node_id}/retry`

request body 第一版可以为空；后面如果要支持“修改 retry 参数”再扩。

response：完整 session detail snapshot。

后端实现步骤：

```text
1. 查 assistant node，校验 role=assistant
2. 找 assistant.parent(user)
3. 在同一 parent 下创建新的 assistant sibling：
	 - version_group_id 复用旧 assistant
	 - version_index 在事务内按 group max + 1 计算，并依赖 `UNIQUE(session_id, version_group_id, version_index)` 防重；冲突则本次创建重试
	 - source_kind = retry
	 - source_node_id = old assistant node id
	 - status = streaming 或 pending
4. 更新 `chat_version_selections` 中该 version_group 的 selected_node_id = new assistant node
5. 更新 sessions.current_leaf_node_id = new assistant node
6. 若 retry 接口本身只负责建节点，则返回 snapshot
7. 若 retry 接口同时触发生成，则把 new assistant node 交给 stream pipeline 继续写内容
```

这里建议第一版把“建重试版本节点”和“开始生成”拆成 service 内两步，但对外仍保持一个接口。这样测试里可以分别断言建树逻辑和流式填充逻辑。

### 6.4 `PATCH /sessions/{session_id}/nodes/{user_node_id}/edit`

request body 建议：

```json
{
	"content": "edited user message"
}
```

response：完整 session detail snapshot。

后端实现步骤：

```text
1. 查 user node，校验 role=user
2. 在同一 parent 下创建新的 user sibling：
	 - version_group_id 复用旧 user node
	 - version_index 在事务内按 group max + 1 计算，并依赖唯一约束冲突重试
	 - source_kind = user_edit
	 - source_node_id = old user node id
	 - content = request.content
3. 不复制旧 user 的 descendants
4. 立即为新 user 创建一个 assistant placeholder 或 pending generation slot
5. 更新 `chat_version_selections` 中 user 版本组 selected_node_id = new user node
6. 更新 sessions.current_leaf_node_id = new assistant placeholder 或其生成完成后的 leaf
7. 返回 snapshot
```

为什么 user edit 要允许 assistant placeholder：

- 它能显式表达“这条新 user 分支已经成为当前分支，下一步该由 assistant 继续生成”
- 对流式 UI 更稳定，前端能看到新分支已经建立，不必等完整输出后才出现

但这里必须补一条失败收敛规则：

- 如果后续 stream 根本没有成功启动，placeholder 不能永远停在 pending / streaming。
- `ConversationTreeService.finalize_stream_turn()` 或对应异常处理必须把 placeholder 置为 `failed`，并写入错误摘要；第一版不建议静默删除占位节点，否则用户会以为编辑操作没发生。

### 6.5 `PATCH /sessions/{session_id}/nodes/{assistant_node_id}/edit`

request body：

```json
{
	"content": "edited assistant message"
}
```

response：完整 session detail snapshot。

后端实现步骤：

```text
1. 查 assistant node，校验 role=assistant
2. 找其 parent user
3. 在同一 parent 下创建新的 assistant sibling：
	 - version_group_id 复用旧 assistant node
	 - version_index 在事务内按 group max + 1 计算，并依赖唯一约束冲突重试
	 - source_kind = assistant_edit
	 - source_node_id = old assistant node id
	 - content = request.content
4. 不复制旧 assistant descendants
5. 更新 `chat_version_selections` 中版本组 selected_node_id = new assistant node
6. 更新 sessions.current_leaf_node_id = new assistant node
7. 返回 snapshot
```

assistant edit 和 retry 的差别，只体现在：

- `source_kind`
- 内容来源不同：retry 走重新生成，assistant edit 走用户手工覆盖

但它们都落在同一个 assistant version group 里。

### 6.6 `POST /chat/stream`

这个接口不一定要改路由路径，但内部调用链必须调整。当前它直接把 `session_id` 传进 agent，然后 agent 自己线性持久化消息；这会绕过树模型。

建议改成：

```text
chat route
	-> ConversationTreeService.prepare_stream_turn(session_id, user_input, provider_id)
			 -> 创建 user node
			 -> 计算本轮可见路径对应的 linearized history
			 -> 返回 {session_id, user_node_id, history_messages}
	-> agent.stream(history + new user message)
	-> 对 token / tool / provider switch 正常产出 SSE
	-> stream 完成时调用 ConversationTreeService.finalize_stream_turn(...)
			 -> 写 assistant node
			 -> 更新 current_leaf_node_id
		  -> 必要时更新 version group selection
	  -> stream 失败时调用 ConversationTreeService.fail_stream_turn(...)
		  -> 将 placeholder 标记为 failed
		  -> 写入错误摘要
		  -> 保持当前路径仍能稳定返回
```

这里最重要的是：

- agent 不直接调用 `SessionStore.add_message()`
- agent 只负责推理和事件流
- tree service 负责把 user/assistant/tool/system 落成 node，并维护当前叶子与版本组选择

### 6.7 为什么这些接口都返回完整 snapshot

因为这里不是局部列表编辑，而是“当前可见对话路径”的切换问题。

只返回 node id 的坏处是：

- 前端要自己重算 visible_path
- 前端要自己找哪些版本组高亮变化了
- 前端和后端一旦对 descendant leaf 选择规则理解不一致，就会刷新后跳回别的分支

所以这几类接口的统一原则应该是：

- mutation 负责修改树
- mutation 结束后立刻调一次 `build_session_detail()`
- route 把完整 snapshot 原样返回前端

## 7. 工程防线

### 7.1 `version_index` 冲突防线

这里底层是 SQLite，第一版不要写成依赖行级锁的思路。应该采用：

- 在 `chat_nodes` 上建立 `UNIQUE(session_id, version_group_id, version_index)`
- 创建新版本节点时在事务内读取当前 max，再尝试插入
- 若触发唯一约束冲突，则重新读取 max 并重试少量次数

这样既符合当前数据库现实，也便于测试并发 retry / edit。

### 7.2 placeholder 失败防线

- user edit 创建 assistant placeholder 后，必须保证有失败收敛路径
- 如果 agent / stream 初始化失败，placeholder 要变成 `failed`
- `GET /sessions/{id}` 返回时，前端应能把这个失败节点渲染为错误块，而不是永久 loading
