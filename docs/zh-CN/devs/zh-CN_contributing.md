# 为 deep-solutions 作贡献

🎉 **感谢您对 deep-solutions 的贡献感兴趣！** 您的贡献让这个项目对每个人都更好。我们欢迎所有形式的贡献 — 错误修复、功能增强、文档改进等。

---

## 📋 目录

- [开始前的准备](#开始前的准备)
- [贡献工作流程](#贡献工作流程)
  - [第 1 步：配置本地开发环境](#第-1-步配置本地开发环境)
  - [第 2 步：创建问题（可选）](#第-2-步创建问题可选)
  - [第 3 步：创建功能分支](#第-3-步创建功能分支)
  - [第 4 步：运行本地测试](#第-4-步运行本地测试)
  - [第 5 步：提交更改](#第-5-步提交更改)
  - [第 6 步：提交拉取请求](#第-6-步提交拉取请求)
  - [第 7 步：评审与合并](#第-7-步评审与合并)
  - [第 8 步：清理](#第-8-步清理)
- [代码标准与约定](#代码标准与约定)
- [常见问题](#常见问题)

---

## 开始前的准备

请花点时间熟悉该项目：

1. **阅读 [Agent 开发指南](zh-CN_agent.md)** — 涵盖项目结构、代码标准、测试和发布过程的综合技术文档。**这是所有贡献者必读的内容。**

2. **查阅 [代码标准](zh-CN_code_standards.md)** — 了解提交约定和 PR 要求。

3. **浏览 [项目结构](zh-CN_project_structure.md)** — 学习依赖关系和项目组织方式。

---

## 贡献工作流程

按照以下步骤贡献新功能或修复：

### 第 1 步：配置本地开发环境

首先，确保您的系统已安装 Python 3.8 和 conda。

```bash
# 克隆仓库
git clone https://github.com/FrostyHec/deep-solutions.git
cd deep-solutions

# 创建开发环境
conda env create -f environment.yml

# 激活环境
conda activate deep-solutions

# 安装包及开发依赖
pip install -e ".[dev]"

# 验证设置
python -c "import deep_solutions; print(deep_solutions.__version__)"
```

> **重要**：继续之前，请先阅读 [Agent 开发指南](zh-CN_agent.md)。它包含关于项目结构、代码规范和最佳实践的必要信息。

### 第 2 步：创建问题（可选）

在开始功能开发前，考虑创建一个问题来：
- 讨论您提议的更改
- 获得维护者的反馈
- 确保符合项目目标

**问题模板**：
- **标题**：功能/修复的简要描述
- **描述**：这解决了什么问题？为什么需要？
- **验收标准**：我们如何知道它完成了？

---

### 第 3 步：创建功能分支

从 `main` 分支创建一个具有描述性名称的分支。

**分支命名约定**：
- 功能：`feature/功能描述`
- 错误修复：`fix/错误描述`
- 文档：`docs/文档描述`
- 示例：
  - `feature/add-tensor-utils`
  - `fix/resolve-import-error`
  - `docs/improve-contributing-guide`

```bash
# 确保您在 main 分支并且是最新的
git checkout main
git pull origin main

# 创建并切换到功能分支
git checkout -b feature/your-feature-name
```

> ⚠️ **重要**：始终从 `main` 创建分支，不要从其他功能分支创建。

---

### 第 4 步：运行本地测试

提交拉取请求之前，确保所有测试在本地通过。

**运行所有检查**：
```bash
bash scripts/check.sh
```

这将执行：
- ✅ 代码格式检查（ruff format）
- ✅ 代码检查（ruff check）
- ✅ 类型检查（mypy）
- ✅ 验证代码/文档中没有中文字符
- ✅ 运行单元测试（pytest）

**其他有用的测试命令**：
```bash
# 只运行单元测试
pytest

# 运行测试并生成覆盖率
pytest --cov=deep_solutions --cov-report=html

# 在多个 Python 版本上测试（3.8-3.12）
tox

# 本地模拟完整 CI 管道
bash scripts/ci-local.sh
```

> ❌ **不要推送**如果任何检查失败。先在本地修复问题。

---

### 提交前检查清单

提交 PR 前，请确认以下事项：

- [ ] **提交约定**：所有提交遵循[约定式提交](zh-CN_commit_conventions.md)格式
- [ ] **所有检查通过**：`bash scripts/check.sh` 无错误完成
- [ ] **测试通过**：`pytest` 无失败运行；新功能已添加单元测试
- [ ] **文档已更新**：如果修改了行为、文件结构或 API，请更新相关文档（EN 和 ZH 版本）
- [ ] **无过时引用**：如果移动/重命名了文件，请更新文档和 README 中的所有交叉引用

---

### 第 5 步：提交更改

遵循项目的提交约定，写出清晰、描述性的提交。

**提交消息格式**（约定式提交）：
```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型**：
- `feat`：新功能
- `fix`：错误修复
- `docs`：文档更改
- `refactor`：代码重构，不涉及功能更改
- `test`：添加或更新测试
- `chore`：依赖更新、配置更改

**示例**：
```bash
git commit -m "feat(core): add new utility function for tensor processing"
git commit -m "fix(utils): resolve edge case in format_output"
git commit -m "docs(contributing): improve contributor guide"
```

> 详细约定见 [提交约定](zh-CN_commit_conventions.md)。

---

### 第 6 步：提交拉取请求

推送您的分支并在 GitHub 上创建 PR。

**推送您的分支**：
```bash
git push origin feature/your-feature-name
```

**在 GitHub 上创建 PR**：
1. 访问仓库：https://github.com/FrostyHec/deep-solutions
2. 点击 **"Pull requests"** 标签
3. 点击 **"New pull request"** 按钮
4. 设置：
   - **Base branch**：`main`
   - **Compare branch**：`feature/your-feature-name`
5. 点击 **"Create pull request"**

**PR 描述模板**：
```markdown
## 描述
简要描述这个 PR 做了什么。

## 相关问题
修复 #123（如果适用）

## 变更
- 变更 1
- 变更 2
- 变更 3

## 测试
您如何测试这个更改？（例如，"在本地运行 pytest，所有测试通过"）

## 检查清单
- [ ] 我已阅读贡献指南
- [ ] 所有测试本地通过（`bash scripts/check.sh`）
- [ ] 代码遵循项目约定
- [ ] 提交消息遵循约定式提交
- [ ] 文档已更新（如适用）
```

**小贴士**：
- ✅ 在 PR 描述中链接相关问题（例如，`Closes #123`）
- ✅ 保持 PR 专注 — 尽可能一个 PR 一个功能
- ✅ 写清晰、描述性的 PR 标题

---

### 第 7 步：评审与合并

提交 PR 后：

1. **CI 检查自动运行**：GitHub Actions 将运行所有测试和检查。在 PR 中检查状态。

2. **代码评审**：维护者将评审您的代码，可能会要求更改。通过以下方式处理反馈：
   ```bash
   # 对您的文件进行更改
   git add .
   git commit -m "refactor: address review feedback"
   git push origin feature/your-feature-name
   ```

3. **批准与合并**：一旦批准且 CI 通过：
   - 维护者将使用 **Squash and Merge** 合并
   - 这将您的所有提交合并为一个清晰的提交
   - 提交消息将遵循约定式提交格式

**合并详情**：
- **策略**：Squash and Merge（保持 `main` 历史清晰）
- **提交消息**：基于您的 PR 标题和描述
- **格式**：`feat(scope): description`（约定式提交）

---

### 第 8 步：清理

**PR 合并后，删除本地和远程分支**：

```bash
# 删除本地分支
git branch -d feature/your-feature-name

# 删除远程分支
git push origin --delete feature/your-feature-name
```

> ⚠️ **重要**：删除后，**永远不要再推送到这个分支**。如果需要进行其他更改，请创建一个新分支。

**验证清理**：
```bash
# 列出本地分支（feature/your-feature-name 不应出现）
git branch -a

# 从远程更新本地分支列表
git fetch --prune
```

---

## 代码标准与约定

贡献时，请遵循以下标准：

### 代码风格
- **格式化工具**：Ruff（`ruff format src/ tests/`）
- **代码检查**：Ruff（`ruff check src/ tests/`）
- **类型提示**：所有函数必须有类型提示（`mypy src/`）
- **Python 版本**：最低 3.8，在 3.8-3.12 上测试

### 命名约定
- 函数/变量：`snake_case`
- 类：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`

### 测试
- 所有新功能必须有单元测试
- 目标代码覆盖率 >80%
- 测试放在 `tests/` 目录

### 文档
- 文档字符串：Google 风格或 NumPy 风格
- 包含示例（如有帮助）
- 如果行为更改，更新 README

### Git 卫生
- ✅ 有意义的提交消息
- ✅ 小的、专注的提交
- ✅ 功能分支中没有合并提交
- ✅ 合并后删除分支

详见 [代码标准](zh-CN_code_standards.md) 和 [提交约定](zh-CN_commit_conventions.md)。

---

## 常见问题

### 问：如果我不是团队成员，我能贡献吗？
**答**：可以！我们欢迎外部贡献者。遵循相同的工作流程 — fork 仓库、创建分支、提交 PR。

### 问：提交 PR 前是否需要创建问题？
**答**：不需要，这是可选的。小的修复可以直接 PR。对于较大的功能，问题讨论很有帮助。

### 问：如果我的 PR 没有通过 CI 怎么办？
**答**：检查 CI 日志（点击失败检查的"详情"）。在本地修复问题，提交并推送到您的分支。PR 将自动更新。

### 问：评审需要多长时间？
**答**：取决于 PR 的复杂性。我们的目标是在 2-3 天内评审。感谢您的耐心！

### 问：提交 PR 后，我可以继续推送到我的分支吗？
**答**：可以！推送更新到同一分支，PR 将自动更新。

### 问：合并后我的提交会发生什么？
**答**：它们将被压缩为一个提交，使用您的 PR 标题/描述作为提交消息，遵循约定式提交格式。

### 问：我不小心推送到了错误的分支。我该怎么办？
**答**：从 `main` 创建一个新的正确分支，挑选您的提交，然后提交一个新的 PR。如果需要帮助，我们可以协助！

---

## 获取帮助

- **有问题？** 打开一个 [issue](https://github.com/FrostyHec/deep-solutions/issues)
- **需要指导？** 查阅 [Agent 开发指南](zh-CN_agent.md) 或 [开发者指南](zh-CN_developers_guide.md)
- **发现错误？** 在 [GitHub Issues](https://github.com/FrostyHec/deep-solutions/issues) 上报告

---

## 🙏 感谢您！

**我们衷心感谢您的贡献！** 无论是代码、文档、错误报告还是功能建议 — 一切都对我们有帮助。开源社区因为像您这样的贡献者而繁荣。

**让我们一起创造美好的东西吧！🚀**

---

*最后更新：2026 年 2 月*
