# Discussion Panel Upgrade — Development Plan

## 1. 用户故事与边界

### 1.1 用户故事

| US | 描述 | 触发点 |
|----|------|--------|
| US-D1 | 用户在生成中可主动中止，并保留已生成内容 | 点击输入框右侧“暂停/中止”按钮 |
| US-D2 | 外部请求失败时，对话显示失败状态，并允许用户基于当前上下文继续发送后续消息 | LLM/API/工具流式请求异常 |
| US-D3 | 思考过程默认折叠显示，debug 模式可展开更多细节 | 助手消息包含 trace/tool call |
| US-D4 | 首轮问答自动生成标题，且标题可手动编辑 | 第一轮 assistant 完成后 |
| US-D5 | 新建 session 时复用 blank session，避免多个空白会话 | 点击左侧加号 |
| US-D6 | 用户可编辑历史 user/assistant 消息并形成分支 | 点击消息下方铅笔 |
| US-D7 | 用户可对 assistant 输出 retry，并在多个版本间切换；编辑历史消息形成的分支也使用同样的标签页式切换体验 | 点击 retry、编辑按钮或左右切换分支 |
| US-D8 | 用户可在设置中开启 debug、管理 API 源与降级顺序；并在对话面板中为当前 session 快速切换 provider | 打开 Settings 或对话面板 Provider Selector |

### 1.2 边界与错误 UX

| 情况 | 预期行为 |
|------|---------|
| 用户主动中止 | 当前 assistant 节点标记为 interrupted，消息尾部展示灰色提示“请求已被用户主动中断” |
| 后端或外部 API 失败 | 当前 assistant 节点标记为 failed，消息尾部展示红色提示“请求失败” |
| 空白 session 再次新建 | 不创建新记录，直接复用当前 blank session |
| 编辑历史消息时当前仍在生成 | 先中止当前生成，再从被编辑节点重新生成新分支 |
| retry 非叶子节点 | 基于该 assistant 的父节点创建同级新版本，并切到新版本 |
| 编辑产生多个分支版本 | 与 retry 产生的多版本一样，统一进入同一个版本组并支持左右切换 |
| debug 关闭 | 前端隐藏合成的系统消息，以及 trace 中的工具输入输出细节 |
| 输入框已有草稿时点击“中止” | 仅中止当前生成，草稿保持不变且不触发发送 |
| 用户主动中止后 | 不提供 Resume API；中断消息以半成品版本保留，下次用户发送新消息时基于当前上下文继续 |
| provider 切换发生在会话中 | 切换结果写入当前 session，后续生成默认沿用该 provider |
| 自动降级关闭 | provider 报错后不自动切换，只保留失败版本并提示错误 |

## 2. 前后端调用链

### 2.1 发送消息与流式生成

```text
用户输入消息
	→ ChatInputBox 触发 useChatStore.sendMessage(draft, sessionId, providerId)
	→ frontend 创建 user 节点 + assistant 占位节点
	→ POST /chat/stream
			 body: { session_id, parent_node_id, provider_id, message, skill, fallback_mode }
	→ backend route → ChatSessionService.start_generation(...)
	→ ReactAgent.stream(...)
	→ SSE 返回 token/thinking/tool/error/interrupted/completed/title_suggestion/provider_switch 事件
	→ frontend 增量更新当前 assistant 节点、trace 面板、session 标题
```

### 2.2 用户主动中止

```text
用户点击“暂停/中止”
	→ frontend AbortController.abort()
	→ POST /sessions/{session_id}/interrupt { node_id, reason: user_cancelled }
	→ backend 将当前 generation 标记为 interrupted
	→ 持久化已生成 token、当前 assistant 内容、失败/中断元数据
	→ frontend 在消息尾部展示灰色提示
	→ 输入框草稿保持原样，按钮恢复发送态
```

### 2.3 编辑 / Retry / 分支切换

```text
用户编辑历史消息或点击 retry
	→ frontend 调用 PATCH /sessions/{session_id}/nodes/{node_id}
			或 POST /sessions/{session_id}/branches/{node_id}/retry
	→ backend 创建新的 sibling/child 节点，更新 session.current_leaf_id
	→ GET /sessions/{session_id}
	→ frontend 依据 current_leaf_id 回溯当前路径，将“编辑产生的版本”和“retry 产生的版本”统一归入版本组，渲染标签页与左右切换器
```

### 2.4 多 API 源与 debug

```text
用户在全局设置中管理 provider 列表、名称、uri、token、debug_mode 与降级顺序
	→ frontend settings store 保存 providers / debug_mode
	→ PUT /settings/llm
	→ backend 将 provider 配置与 LLM 通用设置持久化到 `output/llm_settings.yaml`

用户在对话面板通过 Provider Selector 为当前 session 选择 provider
	→ PATCH /sessions/{id}/preferences { selected_provider_id, fallback_mode }
	→ backend 持久化当前 session 的 selected_provider_id / fallback_mode
	→ 后续所有 /chat/stream 请求显式传递 provider_id；debug_mode 由前端本地决定是否展示 system prompt 与 tool I/O
```

## 3. 架构与数据模型计划

### 3.1 Core 持久化重构

- 用 SQLModel 替换现有手写 `aiosqlite` session store，不做旧数据迁移。
- 会话层至少拆出 `ChatSessionRecord`、`ChatNodeRecord`、`ChatBranchPreferenceRecord`、`ProviderProfileRecord`。
- 当前实现中，`ChatSessionRecord` 保存 `current_leaf_id` 与会话级 provider/fallback 偏好；`debug_mode` 作为全局 LLM runtime 设置保存在 `output/llm_settings.yaml`。
- `ChatSessionRecord` 额外保存 `fallback_mode`，值为 `manual` 或 `auto`。
- `ChatNodeRecord` 用 UUID 主键，核心字段包括 `parent_id`、`role`、`content`、`status`、`branch_group_id`、`version_index`、`trace_payload`、`error_payload`。
- `ChatNodeRecord` 不引入 Resume 状态机；中断后的半成品消息直接作为普通历史节点保存，只通过 `status=interrupted` 区分。
- `ProviderProfileRecord` 至少包含 `id`、`display_name`、`base_url`、`api_key`、`model_name`、`priority`、`is_enabled`。

### 3.1b Provider YAML 结构

```yaml
temperature: 0.0
max_iterations: 10
system_prompt: You are a helpful AI assistant.

providers:
	- id: openai_primary
	  name: OpenAI Primary
	  priority: 0
	  base_url: https://api.openai.com/v1
	  model: gpt-4.1
	  api_key: sk-live-xxx
	  enabled: true

	- id: openai_backup
	  name: OpenAI Backup
	  priority: 1
	  base_url: https://example-proxy/v1
	  model: gpt-4.1-mini
	  api_key: sk-backup-xxx
	  enabled: true
```

约束：

- `name` 用于前端下拉展示与用户选择。
- `id` 用于 API 与数据库持久化。
- `priority` 为整数，`0` 表示最高优先级，数值越大优先级越低。
- YAML 文件路径固定为 `output/llm_settings.yaml`，与数据库等运行期产物一样存放在 output 目录。
- `api_key` 直接以明文形式存储在 YAML 中，前端面板编辑后立即实例化写回该文件。
- `temperature`、`max_iterations`、`system_prompt` 作为 LLM 通用设置，和 providers 一起存放在同一个 YAML 文件中。
- 旧的 env 读取来源 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`MODEL_NAME`、`TEMPERATURE`、`MAX_ITERATIONS`、`SYSTEM_PROMPT` 在实现阶段应全部下线，统一改为从 `output/llm_settings.yaml` 读取。
- 本次迁移范围仅限 LLM API 配置；日志、数据库、embedding 等非 LLM 相关 env 配置保持原样，不纳入这次 YAML 重构。
- `401` 默认不自动降级到“继续重试当前源”，而是将当前源标记为不可用并跳到下一个可用源或直接报错。
- `400` 不触发降级，因为大概率是请求参数或上下文问题。

### 3.2 Frontend 状态重构

- `useChatStore` 从“线性 messages 数组”改为“节点图 + 当前路径投影”。
- session 列表项增加 `isBlank`、`selectedProviderId`、`fallbackMode`、`currentLeafId`。
- 单条消息视图拆分为：最终输出区、可折叠 trace 区、状态提示区、分支操作区。
- 分支操作区必须同时支持两类来源的版本组：`edited` 分支与 `retry` 分支；UI 不区分展示范式，只区分当前版本索引。
- `ChatInputBox` 改为草稿独立存储，不因流式生成而禁用输入。
- `ChatHeader` 或输入框上方增加 `ProviderSelector`，支持 session 级快速切换与“自动降级”选项。
- Provider 管理面板支持拖拽排序；拖拽后更新每个 provider 的 `priority` 字段，并按该顺序在 selector 中展示。

### 3.3 Settings 与 Provider

- 后端配置从单一 `.env` 映射升级为 YAML provider 列表，支持手动选择和自动降级顺序。
- 后端配置从单一 `.env` 映射升级为 `output/llm_settings.yaml`，作为 provider 与 LLM 通用参数的唯一真实来源。
- 前端设置页新增 debug 开关、provider 管理列表、provider 名称编辑、base_url/token/model 配置。
- 当前 debug 开关是全局设置：开启后在对话列表顶部插入合成的 system prompt 消息，并允许在 trace 中展开工具输入输出详情。
- 前端设置页新增 temperature、max_iterations、system_prompt 编辑项。
- 设置页中的 provider 管理列表支持拖拽调整顺序；保存后写回 `output/llm_settings.yaml` 中各 provider 的 `priority`。
- 对话面板新增 provider selector，下拉项展示 provider 名称，并允许为当前 session 选择“自动降级”。
- API 层禁止隐式 provider，所有生成请求必须显式带 `provider_id`。
- 实现阶段必须删除或忽略旧的 env 读取逻辑，确保 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`MODEL_NAME`、`TEMPERATURE`、`MAX_ITERATIONS`、`SYSTEM_PROMPT` 不再作为运行期真实来源。
- `LOG_*`、数据库路径、embedding 相关配置仍继续使用现有 env/.env.example 方案，不在本次调整范围内。

### 3.4 自动降级策略

- 触发降级：`429`、`500`、`502`、`503`、`504`、连接超时、连接建立失败。
- 不触发降级：`400`；`401` 不继续重试当前源，优先标记源不可用并中止或切到其他可用源。
- 自动降级仅在当前 session 的 `fallback_mode=auto` 时启用；若为 `manual`，则任何 provider 错误都不自动切换。
- 如果错误发生在“尚未输出任何 token”阶段，后端可以在当前请求上下文内静默切到下一个 provider，并通过 `provider_switch` trace 事件通知前端。
- 如果错误发生在“已输出部分 token”阶段，不得清空当前失败版本；必须将当前节点标记为 `failed`，然后基于同一父节点自动创建新的 sibling 分支，用降级 provider 重新完整生成。
- 选择下一个 provider 时，按 `priority` 从小到大遍历可用源。
- 前端默认切到新的降级分支版本，同时保留失败的半成品版本供用户切换查看。

## 4. 执行阶段

### Phase 1: Session/Node 模型与 API

- 建立 SQLModel 数据表与 CRUD 服务。
- 实现 session detail 返回树结构、当前叶子、默认展示路径。
- 实现 blank session 复用、标题更新、session title 手动编辑接口。

### Phase 2: Streaming 中断与失败状态

- 为前端流式请求加 `AbortController` 与中断 API。
- 扩展 SSE 事件：`interrupted`、`failed`、`title_suggestion`。
- 扩展 SSE 事件：`provider_switch`，用于记录自动降级轨迹。
- 持久化中断/失败状态、trace 摘要，不引入 resume 指针。

### Phase 3: 分支编辑与 Retry

- 实现 user/assistant 节点编辑、assistant retry、分支切换。
- 前端增加统一的版本标签/左右切换 UI，明确覆盖“编辑分支”和“retry 分支”。
- 默认恢复到 session 上次查看的叶子路径。
- 自动降级在“输出中断”场景下也要复用同一套 sibling 分支模型。

### Phase 4: Debug 与多 Provider

- Settings 面板补 debug 模式与 provider 管理。
- 后端 provider 选择、自动降级策略、会话级 provider 记忆。
- 对话面板落地 provider selector 与“自动降级”选项。
- 完成文档、测试、CI 与 review 收尾。
