# Think 分离测试计划

## 测试策略

本任务不依赖新的外部服务协议，也不需要 dump 策略。测试重点放在三件事：

- backend 是否正确把 `<think>` 从 visible answer 中分离出来
- stream 事件顺序是否满足 ReAct trace 预期
- persistence / replay / frontend 展示是否与用户指南一致

本计划默认以 fresh database 为前提，不包含历史数据迁移验证。

<!-- SECTION:MATRIX -->
## 测试矩阵

| 维度 | 场景 |
|------|------|
| Parser 单元测试 | 单个 `<think>`；多个 `<think>`；无 `<think>`；跨 chunk 标签；未闭合标签 |
| Backend 流式测试 | 纯回答轮次；工具调用轮次；多次 think + 多工具轮次；失败/中断后的 partial response |
| Backend 非流式测试 | `chat()` 返回值；`chat_with_history()` 返回值；CLI 间接依赖的最终字符串 |
| Persistence / Replay | 新会话落库；session refresh；version replay；partial-response 持久化后重新加载 |
| Frontend Store | `TOKEN` 只进正文；`THINKING` 保留完整文本；工具事件顺序保持稳定 |
| Frontend UI | 非 debug 模式下 thinking 可见；debug 模式下工具输入输出细节可见；最终回答不含 `<think>` |
| Manual Smoke | 问候类纯回答；至少一条工具调用问题；刷新页面后的历史回放；debug 开关验证 |

<!-- SECTION:COMMANDS -->
## 计划中的命令验证

### Focused backend

- `packages/core/tests` 中新增或更新 reasoning / stream / session 相关测试
- 优先运行受影响的 backend 测试文件，再扩大到完整后端测试集

### Focused frontend

- 运行 chat store / trace / discussion panel 相关的 Vitest 测试
- 如有必要，再补一个最小的页面级 smoke 验证

### Full gate

- `bash scripts/check.sh`

<!-- SECTION:MANUAL -->
## 手工验收步骤

1. 发送一个无需工具的问候消息。
	- 期望：assistant 正文无 `<think>`；trace 中 thinking 按流式逐步出现。

2. 发送一个明确需要工具的消息。
	- 期望：trace 顺序接近 `LOOP_START -> THINKING -> TOOL_START -> TOOL_END -> THINKING -> LOOP_END`；正文仍只包含最终回答。

3. 在非 debug 模式下展开 trace。
	- 期望：能看到完整 think 文本，但看不到工具输入输出细节。

4. 打开 debug 模式后重试相似场景。
	- 期望：thinking 行为不变，只新增系统消息 / 工具输入输出细节。

5. 刷新页面或重新加载会话。
	- 期望：历史 assistant 正文依旧干净，不会因为 replay 再次出现 `<think>`。

<!-- SECTION:CI -->
## CI 通过标准

- 所有新增/修改的 focused tests 通过
- `bash scripts/check.sh` 通过
- sub-agent review 最终达到 `APPROVED`
- 若 review 提出问题，修复后重跑受影响测试与 `bash scripts/check.sh`
