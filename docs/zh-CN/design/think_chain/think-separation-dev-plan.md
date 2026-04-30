# Think 分离开发计划

## 用户故事与边界

### 用户故事 1: GUI 用户看到干净的最终回答

- Happy path: assistant 正文只显示最终回答；`think` 内容实时进入 ReAct trace，不混入正文。
- Boundary: 如果模型没有输出 `<think>`，界面行为与现在保持一致。
- Boundary: 如果模型输出多个 `<think>` 段，trace 依次追加多个 `THINKING` step。

### 用户故事 2: GUI 用户在非 debug 模式下仍能保留完整 thinking 文本

- Happy path: 非 debug 模式下，thinking 仍完整保留在 trace 中；debug 模式只额外控制系统消息和工具输入输出细节。
- Boundary: trace 默认可折叠，但展开后看到的是完整 think 文本，而不是摘要化截断版本。

### 用户故事 3: 多工具 ReAct 循环的顺序稳定可理解

- Happy path: trace 顺序稳定呈现为 `循环开始 -> think -> 工具 -> think -> 工具 -> think -> 循环结束`。
- Boundary: 某一步如果没有显式 think，可以直接出现工具步骤；某一轮如果没有工具，也允许只出现 `LOOP_START -> THINKING -> LOOP_END`。

### 用户故事 4: CLI 与非流式调用方不再泄漏 `think`

- Happy path: `agent.chat()` 与 `agent.chat_with_history()` 返回值不包含 `<think>` 块。
- Boundary: 本轮不做历史数据迁移，只保证从零初始化的新数据库和新会话行为正确。

<!-- SECTION:CALL_CHAIN -->
## 前后端调用链

### 流式 GUI 链路

```text
用户发送消息
  -> packages/gui/src/api/agent.ts streamMessage()
  -> packages/core/src/agent_core/api/routes/chat.py /chat/stream
  -> packages/core/src/agent_core/engine/agent.py stream*()
  -> ReasoningStreamSplitter 区分 thinking / visible answer
  -> SSE 发出 THINKING / TOKEN / TOOL_* / LOOP_* 事件
  -> packages/gui/src/stores/chat.ts handleStreamEvent()
  -> assistant 正文只累加 TOKEN；trace 追加 THINKING 与工具步骤
```

### 非流式 CLI / 服务链路

```text
CLI 或其他调用方调用 agent.chat()
  -> LangGraph 生成最终 AIMessage.content
  -> 统一 sanitize_visible_answer()
  -> 返回干净的最终回答字符串
```

### 持久化链路

```text
stream/chat 结束
  -> 持久化 assistant message
  -> 后续 session refresh / version replay
  -> 重建后的 assistant.content 仍为已清洗文本
```

所有上下文都必须显式流经调用链：reasoning 分离发生在 backend engine 层，frontend 只消费结构化事件，不自行猜测或二次解析 `<think>`。

<!-- SECTION:SCOPE -->
## 范围与非范围

### 范围内

- 仅支持 `<think>...</think>` 协议
- 为流式和非流式路径提供统一的 reasoning 分离工具
- 保持非 debug 模式下的完整 thinking 文本
- 保证新数据库 / 新会话行为正确
- 为 backend、frontend、session replay 添加回归测试

### 范围外

- 历史会话数据迁移或回填清洗
- provider-native reasoning 字段适配
- thinking 文本摘要化或压缩化展示
- 新增前端协议类型；优先复用现有 `TOKEN` / `THINKING` 事件

<!-- SECTION:WORK_ITEMS -->
## 开发工作项

1. 更新用户指南与任务跟踪文档
	- 更新讨论面板用户指南，明确最终回答 / thinking / debug 的真实行为。
	- 在 `.nonpublic/todo/TODO.md` 增加当前切片的 TODO 与验收标准。

2. 新增 reasoning 分离工具
	- 在 `packages/core/src/agent_core` 下新增 `<think>` 分离与 sanitize 工具。
	- 同时提供完整文本拆分和流式 chunk 拆分两种能力。

3. 改造非流式返回
	- 修改 `chat()` 与 `chat_with_history()`，返回前对 assistant 文本做 sanitize。
	- 保证 CLI 与其它直接调用方拿到的是可见回答，不是原始 reasoning 混合文本。

4. 改造三条流式路径
	- 修改 `stream()`、`stream_with_history()`、`stream_from_messages()`。
	- `TOKEN` 只承载 visible answer；`THINKING` 承载实时 think 文本；顺序符合 ReAct 事件序列。

5. 对持久化与会话刷新做一致性处理
	- 检查正常完成、失败、中断、partial-response、version replay 的 assistant 文本是否都已经清洗。
	- 保证树刷新后不会把 `<think>` 回灌回正文。

6. 保持前端协议稳定，补最小必要回归
	- 仅在需要时调整 `chat.ts` 相关测试，不扩大 UI 重构范围。
	- 非 debug 模式下继续展示完整 thinking，debug 仅控制系统消息与工具 I/O 细节。

7. 完成文档、CI 与 review 工作流
	- 更新设计文档 / 用户指南 / CHANGELOG（若最终代码改动达到需要记录的程度）。
	- 跑 focused tests、`bash scripts/check.sh`、sub-agent review，并迭代到通过。

<!-- SECTION:ACCEPTANCE -->
## 开发完成判定

- assistant 正文不再显示 `<think>` 标签与 think 文本
- thinking 在 ReAct trace 中实时流式输出
- 非 debug 模式仍保留完整 think 文本
- debug 模式只额外显示系统消息与工具输入输出细节
- 多工具循环的 trace 顺序与设计文档一致
- `chat()` / `chat_with_history()` / CLI 输出不泄漏 `<think>`
- 新数据库启动与新会话创建场景下，无需任何迁移即可正确工作
