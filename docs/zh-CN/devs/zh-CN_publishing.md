# PyPI 发布指南

本文档详细说明如何将 `deep-solutions` 包发布到 PyPI 和 TestPyPI。

## 目录
- [概述](#概述)
- [前置准备](#前置准备)
- [版本号管理](#版本号管理)
- [发布到 TestPyPI（测试）](#发布到-testpypi测试)
- [发布到 PyPI（正式）](#发布到-pypi正式)
- [发布后验证](#发布后验证)
- [常见问题](#常见问题)

---

## 概述

本项目使用 **GitHub Actions 工作流** 进行自动化发布，通过手动触发进行发版。

| 场景 | 工作流 | 触发方式 | 目标 |
|------|--------|----------|------|
| 测试发布 | `publish-test.yml` | 手动触发 | TestPyPI |
| 正式发布 | `publish.yml` | 手动触发 | PyPI |

### 版本管理方式

- **版本来源**: Git Tag（如 `v1.0.0`）
- **自动管理**: 使用 `setuptools-scm` 从 Git Tag 生成版本号
- **无需手动维护**: 不需要在代码中手动更新版本号

---

## 前置准备

### 1. 生成 PyPI API Token

#### PyPI 正式环境

1. 登录 [PyPI](https://pypi.org/)
2. 进入 [Account settings → API tokens](https://pypi.org/manage/account/tokens/)
3. 点击 "Add API token"
4. 选择 Scope:
   - `Scope: deep-solutions` - 仅限本项目（推荐）
   - `Scope: Entire account` - 所有项目
5. 复制生成的 token（以 `pypi-` 开头）

#### TestPyPI 测试环境

1. 登录 [TestPyPI](https://test.pypi.org/)
2. 进入 [Account settings → API tokens](https://test.pypi.org/manage/account/tokens/)
3. 重复上述步骤

### 2. 配置 GitHub Secrets

在 GitHub 仓库中配置 Secrets：

1. 进入仓库 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **"New repository secret"**
3. 添加以下 Secrets:

| Secret 名称 | 值 | 说明 |
|-------------|-----|------|
| `PYPI_API_TOKEN` | `pypi-AgE...` | 用于发布到 PyPI |
| `TEST_PYPI_API_TOKEN` | `pypi-AgE...` | 用于发布到 TestPyPI |

### 3. 配置 GitHub Environments

确保已创建以下 Environments：

- `pypi` - 用于正式发布
- `testpypi` - 用于测试发布

> ⚠️ **安全提示**:
> - 不要将 Token 提交到代码仓库
> - 不要在任何文档中公开 Token
> - Token 泄露时应立即重新生成

---

## 版本号管理

### 版本号规范

遵循 [Semantic Versioning](https://semver.org/) 和 [PEP 440](https://peps.python.org/pep-0440/)：

```
vMAJOR.MINOR.PATCH[pre-release]

示例:
- v1.0.0        # 正式版本
- v1.0.0rc1     # Release Candidate
- v1.0.0a1      # Alpha
- v1.0.0b1      # Beta
- v1.0.0.post1  # 后续修复
- v1.0.0.dev1   # 开发版本
```

### 版本号语义

| 类型 | 何时递增 | 示例 |
|------|----------|------|
| MAJOR | 不兼容的 API 变更 | `v1.0.0` → `v2.0.0` |
| MINOR | 向后兼容的功能新增 | `v1.0.0` → `v1.1.0` |
| PATCH | 向后兼容的问题修复 | `v1.0.0` → `v1.0.1` |

### Git Tag 创建

工作流会自动创建 Git Tag，你只需在触发时输入版本号即可。

---

## 发布到 TestPyPI（测试）

在正式发布前，建议先在 TestPyPI 测试。

### 适用场景

- 测试发布流程
- 验证包的构建和安装
- 测试新的版本格式

### 操作步骤

#### 1. 确保代码就绪

```bash
# 确保在正确的分支
git checkout main
git pull origin main

# 运行本地 CI 检查
./scripts/ci-local.sh
```

#### 2. 触发工作流

1. 进入 GitHub 仓库 → **Actions**
2. 选择 **"Publish to TestPyPI"**
3. 点击 **"Run workflow"**
4. 输入版本标签：`v1.0.0-test`、`v1.0.0rc1` 等
5. 点击 **"Run workflow"** 确认

#### 3. 验证安装

```bash
# 从 TestPyPI 安装
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            deep-solutions

# 验证版本
python -c "import deep_solutions; print(deep_solutions.__version__)"
```

---

## 发布到 PyPI（正式）

### 发布前检查清单

- [ ] 所有测试通过
- [ ] 代码已审查并合并到 main
- [ ] CHANGELOG.md 已更新
- [ ] 已在 TestPyPI 测试过

### 操作步骤

#### 1. 触发工作流

1. 进入 GitHub 仓库 → **Actions**
2. 选择 **"Publish to PyPI"**
3. 点击 **"Run workflow"**
4. 输入版本标签：`v1.0.0`
5. 点击 **"Run workflow"** 确认

#### 2. 工作流执行内容

工作流会自动执行：

1. ✅ 在所有 Python 版本 (3.8-3.12) 上运行测试
2. ✅ 创建 Git Tag
3. ✅ 构建 sdist 和 wheel
4. ✅ 发布到 PyPI
5. ✅ 验证安装
6. ✅ 创建 GitHub Release

### 取消/回滚发布

PyPI 不支持覆盖已发布的版本。如果发布了错误版本：

1. **小问题**: 发布 patch 版本修复
2. **严重问题**: 在 PyPI 上 "yank" 该版本（不推荐下载，但仍可安装）

---

## 发布后验证

### 1. 检查 PyPI 页面

访问 https://pypi.org/project/deep-solutions/ 确认：
- 版本号正确
- 描述正确
- 元数据正确

### 2. 测试安装

```bash
# 创建新环境
conda create -n test-install python=3.10 -y
conda activate test-install

# 安装
pip install deep-solutions

# 验证
python -c "import deep_solutions; print(deep_solutions.__version__)"
```

### 3. 检查 GitHub Release

访问仓库的 Releases 页面，确认 Release 已创建。

---

## 常见问题

### Q: 版本号不正确？

**原因**: `setuptools-scm` 从 Git Tag 获取版本

**解决方案**:
1. 确保 Git Tag 格式正确（如 `v1.0.0`）
2. 确保 checkout 时包含完整历史：`fetch-depth: 0`

### Q: Token 无效？

**可能原因**:
- Token 已过期
- Token 作用域不包含该项目
- Secret 名称错误

**解决方案**:
1. 重新生成 Token
2. 更新 GitHub Secret

### Q: 包已存在？

**原因**: PyPI 不允许覆盖已发布的版本

**解决方案**:
- 使用新的版本号
- TestPyPI 上可使用 `--skip-existing` 跳过

### Q: 依赖安装失败？

**可能原因**: 从 TestPyPI 安装时，依赖在 TestPyPI 上不存在

**解决方案**: 使用 `--extra-index-url https://pypi.org/simple/` 从 PyPI 获取依赖

---

## 本地手动发布（备用）

如果需要在本地手动发布（不推荐）：

```bash
# 安装构建工具
pip install build twine

# 创建 Tag
git tag v1.0.0
git push origin v1.0.0

# 构建
python -m build

# 检查
twine check dist/*

# 发布到 TestPyPI
twine upload --repository testpypi dist/*

# 发布到 PyPI
twine upload dist/*
```

---

## 相关文档

- [CI 工作流说明](./zh-CN_ci_workflow.md) - 了解 CI/CD 流程
- [本地测试指南](./zh-CN_local_testing.md) - 发布前测试
- [项目结构](./zh-CN_project_structure.md) - 了解版本管理配置
