# Discussion Panel Upgrade — Test Plan

## 1. 测试矩阵

### 1.1 前端状态与组件

| # | 场景 | 预期 |
|---|------|------|
| F1 | 生成中点击中止 | `AbortController` 生效，当前消息显示 interrupted 灰色提示 |
| F2 | 生成中输入框继续编辑下一条消息 | 输入内容保留，发送按钮切为中止按钮，当前生成不丢草稿 |
| F2b | 输入框已有草稿时点击中止 | 仅中止流式输出，草稿不发送且继续保留 |
| F3 | debug 关闭 | trace 仅显示工具名摘要，合成 system prompt 消息隐藏 |
| F4 | debug 开启 | trace 可展开输入输出，顶部显示当前 skill/default system prompt |
| F5 | 首轮完成后自动标题生成 | header 与 sidebar 显示新标题，允许手工覆盖 |
| F6 | blank session 连续点加号 | session 数量不增长，复用同一 blank session |
| F7 | 编辑历史 user 消息 | 旧链保留，新链成为当前叶子 |
| F8 | retry assistant 消息 | 同一父节点下新增 assistant 版本，可左右切换 |
| F9 | 编辑历史消息后产生多个版本 | 版本组 UI 与 retry 保持一致，可像标签页一样来回切换 |
| F10 | 对话面板切换 provider | 当前 session 的 selectedProviderId 立即更新 |
| F11 | 选择“自动降级” | UI 展示 auto 模式，后续请求带上 fallback_mode=auto |
| F12 | 设置页拖拽调整 provider 顺序 | 面板显示顺序更新，保存后 priority 字段正确重排 |
| F13 | 设置页编辑 temperature/max_iterations/system_prompt | 保存后表单回显正确，后端配置同步更新 |

## 2. 后端与集成测试

### 2.1 Core 持久化与 API

| # | 场景 | 预期 |
|---|------|------|
| B1 | 创建 session 时存在 blank session | 返回已有 blank session，而不是新建记录 |
| B2 | `/chat/stream` 正常完成 | assistant 节点状态为 completed，pending_state 清空 |
| B3 | `/sessions/{id}/interrupt` | assistant 节点状态为 interrupted，半成品内容已入库 |
| B4 | 流式过程中外部 provider 报错 | assistant 节点状态为 failed，错误原因入库 |
| B5 | 编辑历史 user 节点 | 原链保留，新链 leaf 更新为新分支 |
| B6 | retry assistant 节点 | 新 assistant sibling 创建成功，版本组编号正确 |
| B7 | 获取 session detail | 返回节点树、当前 leaf、默认展示路径和标题 |
| B8 | 保存 `debug_mode=false` 的 LLM 设置 | `GET /settings/llm` 回读为 false，前端默认隐藏 system prompt 与 tool I/O |
| B9 | 保存 `debug_mode=true` 的 LLM 设置 | `GET /settings/llm` 回读为 true，前端可展示 system prompt 与 tool I/O |
| B10 | 中断后发送新消息 | 不走 resume API，而是直接在当前上下文上创建新的 user/assistant 节点 |
| B11 | provider 设置 API | 能保存 provider 名称、uri、token 引用、model、顺序、enabled |
| B12 | 无 token 输出即 provider 失败且 auto fallback 开启 | 当前节点直接切到新 provider 完成生成，并写入 provider_switch trace |
| B13 | 已输出部分 token 后 provider 失败且 auto fallback 开启 | 旧节点标记 failed，新建 sibling 节点由新 provider 完整生成 |
| B14 | provider 配置持久化 | 保存后生成 `output/llm_settings.yaml`，priority 顺序与前端拖拽一致 |
| B15 | auto fallback 关闭时 provider 报错 | 不自动切换，当前节点直接 failed |
| B16 | 旧 env 配置存在但 YAML 也存在 | 运行期只采用 YAML，env 不再覆盖实际 LLM 配置 |
| B17 | 非 LLM env 配置仍存在 | log/db/embed 配置继续从 env 读取，不受 llm YAML 改造影响 |

### 2.2 E2E 场景

| # | 场景 | 预期 |
|---|------|------|
| E1 | 发送消息并在中途终止 | 页面显示中断提示，半成品消息保留；下次发送新增下一条消息 |
| E1b | 中断后继续编辑草稿并发送 | 草稿未丢失，新消息基于当前上下文继续对话 |
| E2 | 历史 user 消息编辑后继续生成 | UI 自动跳转到新分支，旧分支可回看 |
| E3 | assistant retry 产生两个版本 | 默认停留在最新版本，可切回旧版本 |
| E3b | 编辑历史消息产生两个版本 | 默认停留在新版本，且可像 retry 版本一样切回旧版本 |
| E4 | 切换 session 再回来 | 恢复到上次查看的叶子路径，而不是简单 latest |
| E5 | 切换 provider 并触发自动降级 | UI 明确显示当前 provider 与降级结果 |
| E6 | 对话开始前 provider 连接失败 | 用户几乎无感，trace 中记录自动切换到下一个 provider |
| E7 | 输出一半时 provider 失败 | 原版本红色失败，新版本自动出现并切到最新标签页 |
| E8 | 未开启自动降级时 provider 失败 | 保留失败版本，不自动切到其他 provider |

## 3. 安全与鲁棒性测试

| # | 攻击/故障向量 | 测试方法 | 预期 |
|---|---------------|---------|------|
| S1 | 编辑消息内容中包含 HTML/脚本 | 构造恶意 markdown/html | 渲染仍经过 DOMPurify，前端不执行脚本 |
| S2 | provider 配置注入非法 base_url | 提交恶意 URL / 空 key | 后端校验失败，不污染全局 provider 列表 |
| S3 | 中断请求与正常完成并发到达 | 人工制造竞态 | 最终状态只能是 completed 或 interrupted 其一，不能双写 |
| S4 | 非 debug 用户查看对话 | 打开 discussion panel | 默认界面不展示 system prompt 与 tool I/O 细节 |
| S5 | blank session 高频新建 | 循环触发 new session | 数据库中空白 session 数量不超过 1 |
| S6 | YAML 明文密钥写入正确性 | 保存 provider 后检查 `output/llm_settings.yaml` | 明文 `api_key` 正确落盘并可被后端读取 |
| S7 | 旧 LLM env 变量残留干扰 | 同时设置 env 与 YAML | 运行时以 YAML 为准，不出现来源混用 |
| S8 | 非 LLM env 配置误迁移 | 同时存在 log/db/embed env | 这些配置行为保持原样，不会被错误并入 llm YAML |

执行顺序：

1. 先做后端单测与 store/API 集成测试。
2. 再做前端 store/组件单测。
3. 最后跑 Playwright E2E 覆盖中断、编辑、retry、provider 切换主链路。
