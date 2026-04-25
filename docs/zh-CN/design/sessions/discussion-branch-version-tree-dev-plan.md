# Discussion Branch Version Tree — Development Plan

## 1. Scope And Ground Truth

本计划只细化 `/large-feature` 中尚未完成的这一块：`branch / edit / retry version tree and unified version`。
目标不是再发明一套“编辑分支 UI”和一套“retry 版本 UI”，而是统一为同一个版本树模型：

- 同一语义槽位的多个候选消息，共享同一个 `version_group_id`。
- `retry`、`编辑 user`、`编辑 assistant`、后续 `auto_fallback` 都只是“产生新版本”的不同来源，UI 不按来源分裂。
- 当前页面展示内容始终由后端返回的 `current_leaf_id + visible_path` 决定，而不是前端自己在本地猜路径。

本计划默认保留现有总设计中的这些约束：

- `current_leaf_id` 仍是 session 级主显示锚点。
- 历史版本不会覆盖旧内容，只能新增 sibling / child 节点。
- 版本切换后刷新页面，必须能恢复到同一条可见路径。

本计划额外采用当前确认过的实现前提：

- 这轮 branch/version tree 改造不要求前向兼容旧 session 数据。
- 开发与测试阶段允许清空数据库后重建 schema，因此优先保证最终模型清晰一致，而不是为了兼容历史脏结构增加过渡层。

## 2. User Stories And Boundary Rules

### 2.1 User Stories

| US | 描述 | Ground Truth |
|----|------|--------------|
| BV1 | 用户对 assistant 点 retry | 在同一父 user 节点下新增 assistant 新版本，并自动切到最新版本。 |
| BV2 | 用户编辑历史 user 消息 | 旧 user 版本保留；新 user 版本进入同一版本组，并从该新版本继续生成新的 assistant 子链。 |
| BV3 | 用户编辑历史 assistant 消息 | 旧 assistant 版本保留；新 assistant 版本进入同一版本组，原后续子链仍挂在旧 assistant 上，新 assistant 默认成为当前叶路径的末端。 |
| BV4 | 用户切换某个版本组中的旧版本 | 当前可见路径切到该版本及其对应默认 descendant leaf，而不是只替换一条消息卡片。 |
| BV5 | 刷新 / 重新进入 session | 页面恢复到上次版本选择后的可见路径，而不是简单落到 latest created node。 |

### 2.2 Boundary Rules

| 情况 | 计划约束 |
|------|---------|
| retry 非当前叶 assistant | 允许；其新版本仍挂在同一父 user 下，但切换当前显示路径到该新版本链。 |
| 编辑 user 且该 user 后面已有长子链 | 不复制旧子链；旧子链仍附着旧 user 版本，新 user 版本从新的 assistant 重新生成。 |
| 编辑 assistant 且该 assistant 后面已有 user/assistant 子链 | 不把旧子链自动克隆到新 assistant；否则会引入“下游内容是否仍可信”的语义歧义。 |
| 切换到旧版本时该版本有多个后续分支 | 后端基于 `ChatBranchPreferenceRecord.selected_leaf_id` 决定默认 descendant；若无记录，则选该版本子树中最新 leaf。 |
| 版本组里有 `retry` 和 `edited` 混合来源 | UI 统一展示成同一组版本 tabs，只在 debug / metadata 中保留来源信息。 |

## 3. Data Model And Call Chain Refinement

### 3.1 Unified Version Model

`ChatNodeRecord` 需要补齐或严格落地这些字段语义：

- `id`: 节点 UUID。
- `parent_id`: 树结构父节点。
- `version_group_id`: 表示“该节点在其语义槽位上的版本组”。同一槽位的多个候选版本共享此值。
- `version_index`: 组内稳定递增序号，只用于排序展示，不用于持久化选择。
- `source_kind`: `initial | retry | user_edit | assistant_edit | fallback`。
- `source_node_id`: 由哪个旧节点派生而来，用于审计和 debug。

`ChatBranchPreferenceRecord` 需要从“模糊的 branch preference”收敛为下面两类显式偏好：

- `(session_id, version_group_id) -> selected_node_id`
- `(session_id, selected_node_id) -> selected_leaf_id`

第二条是关键：它解决“切到旧版本后到底展示它的哪个 descendant leaf”这个问题，避免前端自己猜。

### 3.2 Read Model

`GET /sessions/{session_id}` 不只返回树节点数组，还必须返回一个面向 UI 的 read model：

```text
session detail
	-> current_leaf_id
	-> visible_path: [node_id...]
	-> version_groups: {
			 version_group_id -> {
				 nodes: [...sorted by version_index],
				 selected_node_id,
				 position_in_path,
			 }
		 }
```

这样前端不需要自行从全量树里做不稳定推导；它只负责渲染和发“切换版本”命令。

### 3.3 Mutation Call Chains

#### Retry assistant

```text
用户点击 retry
	-> POST /sessions/{id}/nodes/{assistant_id}/retry
	-> backend 找到 assistant.parent(user)
	-> 在该 user 下创建新的 assistant sibling
	-> 复用 assistant 所在 version_group_id
	-> version_index = group max + 1
	-> current_leaf_id 切到新 assistant（若后续流式完成，再切到其最终 leaf）
	-> 返回新的 session detail snapshot
```

#### Edit historical user

```text
用户编辑历史 user
	-> PATCH /sessions/{id}/nodes/{user_id}/edit
	-> backend 在同一 parent 下创建新的 user sibling
	-> 复用 user 的 version_group_id
	-> 创建新的 assistant generation 占位节点作为其 child
	-> current_leaf_id 指向新分支的最新 leaf
	-> 返回新的 session detail snapshot
```

#### Edit historical assistant

```text
用户编辑历史 assistant
	-> PATCH /sessions/{id}/nodes/{assistant_id}/edit
	-> backend 在同一 parent(user) 下创建新的 assistant sibling
	-> 复用 assistant 的 version_group_id
	-> 不复制旧 assistant 的 descendants
	-> current_leaf_id 切到新 assistant
	-> 之后用户继续对话时，从该新 assistant 往下长新链
```

#### Switch version

```text
用户在版本 tabs 点击旧版本
	-> PATCH /sessions/{id}/version-groups/{group_id}/select { node_id }
	-> backend 更新 selected_node_id
	-> backend 解析该 node 的默认 descendant leaf
	-> current_leaf_id 更新为该 leaf
	-> 返回新的 visible_path + version_groups
```

## 4. Execution Phases And Non-Negotiables

### Phase A: Store / API groundwork

- 明确 `version_group_id`、`source_kind`、`source_node_id` 的最终 schema，按可清库重建前提直接落定，不为旧数据兼容保留中间层。
- 补 `select-version` API，而不是让前端本地切换。
- `session detail` read model 一次性返回 `visible_path + version_groups`。

### Phase B: Edit / Retry mutations

- 先完成 backend 对 `retry`、`edit user`、`edit assistant` 三条 mutation 的统一落模。
- 每条 mutation 都必须返回完整 session snapshot，避免前端拼补丁。

### Phase C: Frontend unified version UI

- 单条消息下方只保留一套版本组 UI：tabs + 左右切换器。
- UI 文案不区分“这是 retry 版本”还是“这是 edit 版本”；只在 debug metadata 中显示来源。
- 切换版本后，消息列表整体投影切换到新的 `visible_path`。

### Phase D: Fallback compatibility

- 本阶段先不要求把 fallback 全量实现到版本组 UI，但数据模型必须预留 `source_kind=fallback`。
- 后续 partial-failed fallback 直接复用 assistant sibling 版本组，不再发明新结构。

### Non-Negotiables

- 不允许前端仅靠 render order 推断版本选择。
- 不允许 edit / retry 只改一条消息展示而不更新 `current_leaf_id`。
- 不允许 assistant edit 自动复制旧 descendants，这会引入错误的“继承可信性”。
- 实现阶段必须先做 store/API focused tests，再做前端 tabs UI。
