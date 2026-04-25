# Discussion Branch Version Tree — Test Plan

## 1. Backend Store And Read-Model Tests

测试前提：本轮不要求验证旧 session 数据迁移兼容；fixture 可以直接按新 schema 建库或清库后初始化。

### 1.1 Store-level invariants

| ID | 场景 | 预期 |
|----|------|------|
| S-BV1 | 新建初始线性对话 | 每个 node 有稳定 `version_group_id`；初始版本 `version_index=0`。 |
| S-BV2 | assistant retry | 在同一父 user 下新增 assistant sibling，`version_group_id` 相同、`version_index` 递增。 |
| S-BV3 | edit historical user | 新 user sibling 进入同一组；旧 descendants 保留在旧 user 下，新 user 默认无旧 descendants。 |
| S-BV4 | edit historical assistant | 新 assistant sibling 进入同一组；旧 assistant descendants 不被复制。 |
| S-BV5 | select-version 后计算 visible leaf | backend 返回的 `current_leaf_id` 落在所选 node 子树内。 |
| S-BV6 | refresh after select-version | 同一 session detail 再读取，`visible_path` 与上次选择保持一致。 |
| S-BV7 | 离开旧版本时写 bookmark | 旧 node 的 bookmark 被保存，但版本组当前 selected node 不被覆盖错乱。 |
| S-BV8 | 并发 retry / edit 创建新版本 | `version_index` 不重复；若冲突发生，重试后仍得到递增版本号。 |

### 1.2 API-level tests

| ID | 场景 | 预期 |
|----|------|------|
| A-BV1 | `POST /nodes/{assistant_id}/retry` | 返回完整 session snapshot，包含新 assistant 版本与更新后的 `current_leaf_id`。 |
| A-BV2 | `PATCH /nodes/{user_id}/edit` | 返回完整 snapshot，新 user 版本成为可见路径的一部分。 |
| A-BV3 | `PATCH /nodes/{assistant_id}/edit` | 返回完整 snapshot，新 assistant 版本成为路径末端。 |
| A-BV4 | `PATCH /version-groups/{group_id}/select` | 返回新的 `visible_path` 与 `selected_node_id`。 |
| A-BV5 | 选择不存在的 `node_id` | 4xx，且不污染 branch preference。 |
| A-BV6 | 切换版本后恢复旧 node bookmark | 再切回该 node 时，优先落到其 bookmark leaf，而不是错误覆盖成当前 group 选择。 |
| A-BV7 | user edit 后 stream 启动失败 | placeholder 节点转为 failed，不会永久停在 pending/loading。 |

## 2. Frontend State And Component Tests

### 2.1 Store projection tests

| ID | 场景 | 预期 |
|----|------|------|
| F-BV1 | 收到 session snapshot | chat store 直接使用 `visible_path` 渲染，不再本地猜测。 |
| F-BV2 | 点击 retry 后收到新 snapshot | 当前消息列表切到新 assistant 版本。 |
| F-BV3 | 点击旧版本 tab | 触发 select-version API；store 用返回 snapshot 替换投影。 |
| F-BV4 | 刷新 session detail | 版本选择状态和上次一致。 |

### 2.2 Component tests

| ID | 场景 | 预期 |
|----|------|------|
| C-BV1 | 单个版本组渲染多个版本 | tabs 顺序按 `version_index`，当前版本高亮。 |
| C-BV2 | 版本来源混合（retry + edit） | UI 不分裂成两套控件，仍是一套统一 tabs。 |
| C-BV3 | 切换版本后消息树重投影 | 旧路径消息消失，新路径消息出现。 |
| C-BV4 | assistant edit 后无 descendants | UI 不错误复用旧 assistant 之后的子消息。 |

## 3. E2E And Manual Scenarios

| ID | 场景 | 预期 |
|----|------|------|
| E-BV1 | 正常对话 → retry assistant | 自动出现新版本，默认停留最新版本，可切回旧版本。 |
| E-BV2 | 编辑中间 user 消息 | 新分支生成后，旧分支仍可回看。 |
| E-BV3 | 编辑中间 assistant 消息 | 新 assistant 成为当前路径末端；旧 assistant 子链仅在切回旧版本时出现。 |
| E-BV4 | 多层版本切换后刷新页面 | 页面恢复到刷新前那条可见路径。 |
| E-BV5 | 在旧版本基础上继续发消息 | 新消息挂到当前所选版本路径，而不是误挂到 latest 版本。 |
| E-BV6 | user edit 后大模型调用失败 | 页面显示 failed assistant 占位，而不是永久 loading。 |

## 4. Test Execution Order And Exit Criteria

### Execution order

1. 先做 store / service / API focused tests，确保数据模型和 `current_leaf_id` 语义稳定。
2. 再做 frontend store / component tests，验证 unified version tabs 只消费 backend snapshot。
3. 最后做 Playwright E2E，覆盖 retry、edit user、edit assistant、switch-version、refresh restore。

### Exit criteria

- backend tests 覆盖三类 mutation：`retry`、`edit user`、`edit assistant`。
- 至少一条 API test 验证 `select-version` 真正更新 `current_leaf_id`。
- 至少一条前端测试验证 UI 不按来源拆成两套版本控件。
- 至少一条 E2E 验证刷新后版本选择不丢。
- broad CI 之前，不允许把这部分只停留在“能新建 sibling node”，而没有把 read model 和 visible path 走通。
