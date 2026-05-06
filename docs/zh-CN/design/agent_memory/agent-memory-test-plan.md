# Agent Memory 测试计划

## 测试策略

本功能不依赖第三方网络协议，因此不需要外部服务 dump。测试重点集中在三个方面：

- 文件根目录推导是否正确，尤其是 `db_path` 与 `:memory:` 两种模式
- 文件安全与一致性是否成立，包括非法文件名、越界路径、rewrite 备份、并发更新
- 工具输出是否足够稳定，能支持模型先列出主题、再读取、再更新的工作流

## 测试矩阵

| 维度 | 场景 |
|------|------|
| Service 单元测试 | 空目录列表；创建新文件；读取文件；append 更新；rewrite 更新；备份生成；时间戳刷新 |
| 安全测试 | 恶意文件名如 `../../secret`；隐藏文件名；超长文件名；非法字符；根目录逃逸校验 |
| Frontmatter 解析 | tags 为空；summary 含中文与 YAML 特殊字符；正文含 `---` 分隔线 |
| Provider / 生命周期 | `db_path=':memory:'` 使用临时目录；关闭依赖后 provider 单例被清空 |
| Tool 集成测试 | list/read/create/update 返回可解析 JSON 或文本；缺失文件时错误信息稳定 |
| 回归测试 | `.backup/` 不出现在主题列表；非 `.md` 文件不被误识别 |

## 计划中的命令验证

- 优先新增或更新 `packages/core/tests` 下的 memory service / tool 相关测试文件
- 先运行 focused pytest，再扩大到完整后端测试集
- 最终运行 `bash scripts/check.sh`

## 手工验收步骤

1. 让 agent 记住一条新事实。
	- 期望：`output/agent_memory/` 下新增 `.md` 文件，包含合法 Frontmatter 和正文。

2. 询问 agent 当前记住了哪些主题。
	- 期望：返回摘要列表，不包含 `.backup/` 项。

3. 再次补充同一主题。
	- 期望：append 模式追加内容，不破坏原有正文。

4. 触发 rewrite 场景。
	- 期望：正文被重写，`.backup/` 下出现旧版本备份。

5. 尝试用恶意文件名或路径更新。
	- 期望：请求被拒绝，错误信息明确。

## CI 通过标准

- 所有新增 / 修改的 focused tests 通过
- `bash scripts/check.sh` 通过
- 若后续 review 提出实现问题，修复后需重跑受影响的 focused tests 与完整检查脚本
