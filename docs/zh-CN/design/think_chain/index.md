# Think 链路分离计划

## 背景

当前部分模型会把推理内容直接写进 `AIMessage.content`，常见形式为：

```text
<think>...</think>

最终回答
```

这与当前产品设计意图不一致。现有讨论面板设计已经明确：思考过程应进入 ReAct trace，默认折叠显示；用户可见的最终回答只保留可直接阅读的结果文本。

本页记录问题分析、实现方案与当前落地约束。当前代码已经按本文方案实现 `<think>` 协议的分离：最终回答保留在 assistant 正文，thinking 文本进入 ReAct trace，并兼容新数据库下的会话持久化与 replay。

## 相关计划

- 开发计划：`think-separation-dev-plan.md`
- 测试计划：`think-separation-test-plan.md`

<!-- SECTION:FLOW -->
## 现状链路

### 1. 后端流式层会先把所有文本当作最终回答输出

`packages/core/src/agent_core/engine/agent.py` 当前在 `stream`、`stream_with_history`、`stream_from_messages` 三条流式路径里都采用同样的逻辑：

- `on_chat_model_stream` 中，只要 `chunk.content` 非空，就直接 `yield TokenEvent(content=content)`
- `on_chat_model_end` 中，如果 `ai_msg.tool_calls and ai_msg.content`，再额外 `yield ThinkingEvent(content=str(ai_msg.content))`

这意味着：只要模型把 `<think>...</think>` 放进普通文本通道，该内容就会先作为 `token` 被前端追加到最终回复中。

### 2. 前端把 `token` 无条件并入 assistant 正文

`packages/gui/src/stores/chat.ts` 的 `handleStreamEvent()` 里：

- `TOKEN` 事件会执行 `msg.content += event.content`
- `THINKING` 事件才会进入 `msg.traceSteps`

因此，只要后端没有先完成拆分，前端就没有机会把推理文本从最终回答里剥离出来。

### 3. trace 展示层其实已经存在

`packages/gui/src/components/chat/ChatTraceBlock.vue` 已经有 `THINKING` 的独立渲染分支，因此 UI 本身并不缺“思维过程展示位置”，缺的是正确的数据分流。

### 4. 非流式路径也会泄漏 `think`

`packages/core/src/agent_core/engine/agent.py` 的 `chat()` 和 `chat_with_history()` 直接返回 `str(last_message.content)`。

`packages/cli/src/agent_cli/main.py` 的交互式 CLI 正是走 `agent.chat()`，所以这个问题不仅影响 GUI 的 SSE 流式消息，也影响 CLI 的最终回答文本。

### 5. 持久化层只有标题生成做了局部清洗

`packages/core/src/agent_core/services/conversation_tree_service.py` 里已经有 `_TITLE_REASONING_BLOCK_PATTERNS`，用于标题生成前清理 `<think>` 块。

这说明仓库已经承认“reasoning 泄漏”是一个真实问题，但目前只在 title generation 上做了局部补丁，普通回答内容和会话持久化仍没有统一清洗。

<!-- SECTION:ROOT_CAUSE -->
## 根因分析

### 根因 A: 模型把 reasoning 和 final answer 混在同一个文本通道

从 `packages/cli/output/logs/agent.log` 可以直接看到多种原始输出：

- 纯回答轮次：`AIMessage(content='<think>...</think>\n\n最终回答', tool_calls=[])`
- 工具调用轮次：`AIMessage(content='<think>...</think>\n\n', tool_calls=[...])`
- 多轮工具后收束：一个最终 `AIMessage.content` 中可能累积多个 `<think>` 块

也就是说，问题并不是前端单独制造出来的，而是 provider/model 原始输出就已经把 reasoning 混进了 `content`。

### 根因 B: 流式协议缺少“可见回答”和“思维过程”两个独立缓冲区

当前后端协议虽然定义了 `TokenEvent` 和 `ThinkingEvent`，但真正执行时仍然是“先把所有文本当 token 发出去，再在某些条件下补发 thinking”。

这不是分流，而是事后补记。

### 根因 C: `ThinkingEvent` 触发条件过窄

现在只有 `ai_msg.tool_calls and ai_msg.content` 时才发 `ThinkingEvent`。因此：

- 工具调用前的 reasoning 会重复出现一次：先泄漏进 `token`，再作为 `thinking` 出现
- 没有工具调用的普通回答轮次，reasoning 只会泄漏到最终回答里，根本不会进入 trace

### 根因 D: 会话持久化没有统一 sanitize

即使前端流式阶段临时规避了可见泄漏，只要最终落库的 `AIMessage.content` 仍保留 `<think>`，下一次从会话树重建消息时，问题还会重新出现。

<!-- SECTION:PLAN -->
## 修改计划

## 目标

- 最终回答正文不再包含 `<think>` 标签和推理文本
- 推理文本进入现有 ReAct trace，复用 `THINKING` 展示能力
- 工具调用轮次和非工具调用轮次都采用统一规则
- 会话持久化保存的是已清洗的 assistant 可见文本，避免历史分支回放再次泄漏
- 尽量不扩大前端协议改动，优先在后端完成分流

## 方案选择

### 方案 1: 只在前端渲染时 strip `<think>`

不采用。原因：

- 流式过程中已经把 reasoning 作为 `token` 发给前端，用户在过程中仍会看到泄漏
- CLI 与其他非前端调用方仍会继续泄漏
- 持久化内容仍是脏数据

### 方案 2: 只在 `CHAT_MODEL_END` 结束时后处理整个答案

不作为主方案。它可以修复最终落库结果，但无法修复“流式过程中先泄漏”的问题。

### 方案 3: 后端引入统一的 reasoning 分流器，在流式和非流式两条路径共用

建议采用。这是最接近根因的修复方式。

## 分阶段实施

### 阶段 1: 新增统一的 reasoning 解析工具

在 `packages/core/src/agent_core` 下新增一个轻量工具模块，职责包括：

- `split_reasoning_blocks(text)`：把完整文本拆成 `thinking_segments` 与 `visible_text`
- `sanitize_visible_answer(text)`：去除 `<think>` 块后返回用户可见回答
- `ReasoningStreamSplitter`：支持增量喂入 chunk，处理标签跨 chunk 边界的情况

这个模块应当保持 provider 无关，只关心“当前已观测到的 `<think>...</think>` 协议”。

### 阶段 2: 改造流式路径

修改 `packages/core/src/agent_core/engine/agent.py` 中三条流式方法：

- `on_chat_model_stream`
	- 先把 `chunk.content` 送入 `ReasoningStreamSplitter`
	- 仅将“用户可见片段”转成 `TokenEvent`
	- 对已闭合的 reasoning 片段发出 `ThinkingEvent`
- `on_chat_model_end`
	- flush 剩余缓冲
	- 若最后仍有 reasoning 片段，补发 `ThinkingEvent`
	- 对要持久化的 `AIMessage.content` 做 sanitize，避免脏数据进入历史

修复后应满足：

- 工具前 reasoning 只进入 trace 一次
- 普通回答轮次中的 reasoning 也能进入 trace，而不是混进正文
- 未包含 `<think>` 的模型输出继续按现状工作

### 阶段 3: 改造非流式返回值

修改 `chat()` 与 `chat_with_history()`：

- 返回前对 `last_message.content` 做同一套 sanitize
- 持久化前同样保存清洗后的 assistant 文本

这样 CLI 的 `agent.chat()` 结果也会同步修复，不需要单独改 CLI 展示逻辑。

### 阶段 4: 对会话树与中断恢复做一致性处理

检查以下路径是否都使用清洗后的 assistant 文本：

- 正常完成后的消息持久化
- 中断后的 partial response 持久化
- 失败后的 partial response 持久化
- 会话树重建时的消息回放

这里的目标不是新增前端逻辑，而是确保“树刷新是权威数据源”时，权威数据本身已经干净。

### 阶段 5: 前端仅做回归验证，尽量不改协议

前端 `packages/gui/src/stores/chat.ts` 和 `packages/gui/src/components/chat/ChatTraceBlock.vue` 原则上可以不改协议：

- `TOKEN` 继续作为最终回答正文
- `THINKING` 继续进入 trace

如果后端分流正确，前端主要需要补回归测试，而不是大改实现。

<!-- SECTION:TESTS -->
## 测试计划

### 后端单元测试

为新的 reasoning 解析工具补以下场景：

- 单个 `<think>...</think>` + 最终回答
- 多个 `<think>` 块串联
- 标签被拆在多个 stream chunk 里，例如 `<thi` / `nk>`
- 只有 reasoning、没有可见正文的工具调用轮次
- 未闭合标签或异常格式时的保守降级行为

### 后端集成测试

优先补到 `packages/core/tests`：

- 流式测试：断言 `token` 中不再出现 `<think>` 内容，`thinking` 事件正确出现
- 非流式测试：断言 `chat()` / `chat_with_history()` 返回值不含 reasoning
- 会话持久化测试：断言刷新后的 session detail 中 assistant `content` 已清洗
- 维持既有标题测试：保证 title sanitize 逻辑仍然成立

### 前端测试

优先补到现有 chat store / chat trace 相关测试：

- `TOKEN` 只追加最终回答
- `THINKING` 仍进入 `traceSteps`
- 现有 trace block 在默认折叠模式下仍只显示摘要与工具步骤

### 验收场景

至少做三类人工验收：

- 纯对话问候：最终回答不显示 `<think>`，trace 有或无 `thinking` 都必须与设计一致
- 工具调用问答：工具前 reasoning 只在 trace 出现一次
- 中断/刷新/回放：重新加载 session 后不出现历史 `think` 泄漏

### 验收时的功能表现

本次修改完成后，用户在讨论面板里看到的结构应明确分成两层：

- assistant 正文区域：只显示最终回答，不显示 `<think>` 标签和推理文本
- ReAct trace 区域：显示循环过程中的思维与工具步骤

当一轮回答包含多次思考和多次工具调用时，trace 的期望顺序应接近下面这个模型：

```text
LOOP_START
THINKING
TOOL_START
TOOL_END
THINKING
TOOL_START
TOOL_END
THINKING
LOOP_END
```

也就是说，用户感知到的顺序应是：

- 循环开始
- think 文本
- 调用工具 1
- 工具 1 结果
- think 文本
- 调用工具 2
- 工具 2 结果
- think 文本
- 循环结束

补充约束如下：

- 每段 `thinking` 只在 trace 中出现一次，不能同时出现在 assistant 正文里
- 最终回答应在 trace 之外单独显示，不应被包进 `THINKING` step
- 如果该轮没有工具调用，则允许退化为 `LOOP_START -> THINKING -> LOOP_END + 最终回答`
- 如果某一步没有显式 reasoning，而是直接调用工具，也允许出现 `LOOP_START -> TOOL_START -> TOOL_END -> ... -> LOOP_END`

<!-- SECTION:QUESTIONS -->
## 待确认问题

1. 这一轮是否只支持 `<think>...</think>` 协议，还是要顺手为后续 provider-native reasoning 字段预留接口。
2. `THINKING` 在非 debug 模式下是否继续显示完整文本，还是改成摘要化展示。当前设计文档倾向于默认折叠，但文本本身仍然是完整的。
3. 历史会话是否需要一次性回填清洗。当前建议是先做 forward-only 修复，避免把本轮任务扩成数据迁移。
