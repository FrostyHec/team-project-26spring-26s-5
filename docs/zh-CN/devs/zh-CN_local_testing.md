# 本地测试指南

本文档介绍 `deep-solutions` 项目的本地测试方法，包括各种脚本和工具的使用。

## 目录
- [测试方法概览](#测试方法概览)
- [快速检查脚本 (check.sh)](#快速检查脚本-checksh)
- [CI 模拟脚本 (ci-local.sh)](#ci-模拟脚本-ci-localsh)
- [Tox 多版本测试](#tox-多版本测试)
- [单独运行测试工具](#单独运行测试工具)
- [测试方法对比](#测试方法对比)
- [常见问题](#常见问题)

---

## 测试方法概览

项目提供多种本地测试方法，适用于不同场景：

| 方法 | 命令 | 用途 | 耗时 |
|------|------|------|------|
| **快速检查** | `./scripts/check.sh` | 日常开发，提交前检查 | ~30 秒 |
| **CI 模拟** | `./scripts/ci-local.sh` | 创建 PR 前完整验证 | ~1-2 分钟 |
| **Tox 单版本** | `tox -e py38` | 测试特定 Python 版本 | ~30 秒 |
| **Tox 全矩阵** | `tox -p auto` | 发布前完整测试 | ~2-5 分钟 |
| **单独工具** | `pytest` / `ruff` / `mypy` | 针对性调试 | 视情况而定 |

---

## 快速检查脚本 (check.sh)

### 用途

日常开发时的一键检查脚本，**推荐在每次提交前运行**。

### 使用方法

```bash
./scripts/check.sh
```

### 执行步骤

脚本会依次执行以下检查：

| 步骤 | 工具 | 功能 |
|------|------|------|
| 1 | `ruff format` | 自动格式化代码 |
| 2 | `ruff check` | Lint 检查 |
| 3 | `mypy` | 类型检查 |
| 4 | `pytest` | 运行测试 |

### 特点

- ✅ **自动格式化**: 会自动修复格式问题
- ✅ **快速反馈**: 失败时立即停止
- ✅ **彩色输出**: 清晰显示每个步骤的状态

### 示例输出

```
========================================
  deep-solutions 代码检查脚本
========================================

项目目录: /path/to/deep-solutions

============================================================
  Step 1/4: 代码格式化 (ruff format)
============================================================

正在格式化 src/ 和 tests/ ...
✓ 代码格式化完成

============================================================
  Step 2/4: Lint 检查 (ruff check)
============================================================

正在检查代码问题...
✓ Lint 检查通过

...
```

---

## CI 模拟脚本 (ci-local.sh)

### 用途

模拟 CI 的完整检查流程，**推荐在创建 PR 前运行**。

### 使用方法

```bash
./scripts/ci-local.sh
```

### 执行步骤

脚本模拟 CI 的所有步骤：

| 步骤 | 内容 | 对应 CI Job |
|------|------|-------------|
| 1 | 格式检查 (`ruff format --check`) | lint |
| 2 | Lint 检查 (`ruff check`) | lint |
| 3 | 类型检查 (`mypy`) | type-check |
| 4 | 运行测试 + 覆盖率报告 | test |
| 5 | 构建包 + 检查 | build |

### 与 check.sh 的区别

| 区别 | check.sh | ci-local.sh |
|------|----------|-------------|
| 格式化 | 自动修复 | 仅检查（不修改） |
| 构建检查 | ❌ 不包含 | ✅ 包含 |
| 生成报告 | ❌ 不生成 | ✅ 生成 junit + coverage |
| 适用场景 | 日常开发 | PR 前验证 |

### 生成的文件

成功执行后会生成：
- `pytest-report.xml` - 测试报告
- `coverage.xml` - 覆盖率报告
- `dist/` - 构建产物

---

## Tox 多版本测试

### 什么是 Tox？

Tox 是 Python 的自动化测试工具，用于在多个 Python 版本中运行测试。

### 安装

Tox 已包含在开发依赖中：

```bash
pip install -e ".[dev]"
```

### 基本用法

#### 测试当前 Python 版本

```bash
tox -e py
```

#### 测试特定 Python 版本

```bash
# Python 3.8
tox -e py38

# Python 3.9
tox -e py39

# Python 3.10
tox -e py310

# Python 3.11
tox -e py311

# Python 3.12
tox -e py312
```

#### 全矩阵测试

```bash
# 串行运行所有版本
tox

# 并行运行（推荐）
tox -p auto
```

> **注意**: 需要在系统中安装相应的 Python 版本。缺失的版本会自动跳过。

### 其他测试任务

```bash
# Lint 检查
tox -e lint

# 类型检查
tox -e type

# 构建包
tox -e build

# 文档构建
tox -e docs
```

### 传递参数给 pytest

使用 `--` 传递额外参数：

```bash
# 运行特定测试文件
tox -e py38 -- tests/test_core.py

# 运行特定测试函数
tox -e py38 -- tests/test_core.py::test_hello_world

# 详细输出
tox -e py38 -- -v

# 在第一个失败处停止
tox -e py38 -- -x
```

### Tox 环境说明

`tox.ini` 定义了以下环境：

| 环境 | 用途 | 命令 |
|------|------|------|
| `py38`-`py312` | 运行测试 | `pytest --cov=deep_solutions` |
| `lint` | 代码检查 | `ruff format --check` + `ruff check` |
| `type` | 类型检查 | `mypy src/` |
| `build` | 构建检查 | `python -m build` + `twine check` |
| `docs` | 文档构建 | `sphinx-build` |

### 安装多个 Python 版本

#### 使用 Conda

```bash
# 创建多个环境
conda create -n py38 python=3.8 -y
conda create -n py39 python=3.9 -y
conda create -n py310 python=3.10 -y
conda create -n py311 python=3.11 -y
conda create -n py312 python=3.12 -y

# 将 Python 可执行文件添加到 PATH
export PATH="$HOME/miniconda3/envs/py38/bin:$PATH"
export PATH="$HOME/miniconda3/envs/py39/bin:$PATH"
# ... 以此类推
```

#### 使用 pyenv

```bash
# 安装多个版本
pyenv install 3.8.18
pyenv install 3.9.18
pyenv install 3.10.13
pyenv install 3.11.7
pyenv install 3.12.1

# 设置本地版本
pyenv local 3.8.18 3.9.18 3.10.13 3.11.7 3.12.1
```

---

## 单独运行测试工具

### pytest - 单元测试

```bash
# 运行所有测试
pytest

# 运行特定文件
pytest tests/test_core.py

# 运行特定测试
pytest tests/test_core.py::test_hello_world

# 详细输出
pytest -v

# 显示 print 输出
pytest -s

# 覆盖率报告
pytest --cov=deep_solutions --cov-report=html

# 在失败处停止
pytest -x

# 重新运行上次失败的测试
pytest --lf
```

### ruff - 代码格式化和 Lint

```bash
# 格式化代码
ruff format src/ tests/

# 检查格式（不修改）
ruff format --check src/ tests/

# Lint 检查
ruff check src/ tests/

# 自动修复
ruff check --fix src/ tests/

# 显示规则解释
ruff rule E501
```

### mypy - 类型检查

```bash
# 检查 src 目录
mypy src/

# 检查特定文件
mypy src/deep_solutions/core.py

# 详细输出
mypy src/ --verbose

# 生成报告
mypy src/ --html-report mypy-report
```

### 语言与文档检查

```bash
# 仅检查源码语言
python scripts/check_language.py --source-only

# 仅检查文档（双语结构 + 断链）
python scripts/document_checker.py

# 所有语言和文档检查
python scripts/check_language.py -v
```

---

## 测试方法对比

### 选择指南

| 场景 | 推荐方法 |
|------|----------|
| 日常开发，提交前快速检查 | `./scripts/check.sh` |
| 创建 PR 前完整验证 | `./scripts/ci-local.sh` |
| 测试特定 Python 版本 | `tox -e py38` |
| 发布前完整回归测试 | `tox -p auto` |
| 调试特定测试失败 | `pytest tests/test_xxx.py -v` |
| 修复 Lint 问题 | `ruff check --fix src/` |

### 功能对比

| 功能 | check.sh | ci-local.sh | tox | 单独工具 |
|------|----------|-------------|-----|----------|
| 格式化 | 自动修复 | 仅检查 | 可配置 | 可配置 |
| Lint | ✅ | ✅ | ✅ | ✅ |
| 类型检查 | ✅ | ✅ | ✅ | ✅ |
| 测试 | ✅ | ✅ | ✅ | ✅ |
| 多版本 | ❌ | ❌ | ✅ | ❌ |
| 构建 | ❌ | ✅ | ✅ | 需手动 |
| 隔离环境 | ❌ | ❌ | ✅ | ❌ |

---

## 常见问题

### Q: check.sh 权限不足？

```bash
chmod +x scripts/check.sh
chmod +x scripts/ci-local.sh
```

### Q: tox 找不到 Python 版本？

确保 Python 可执行文件在 PATH 中，或使用 `skip_missing_interpreters = true`（已在 tox.ini 中配置）。

### Q: 测试覆盖率不够？

查看覆盖率报告定位未覆盖的代码：

```bash
# 生成 HTML 报告
pytest --cov=deep_solutions --cov-report=html

# 打开报告
xdg-open htmlcov/index.html  # Linux
open htmlcov/index.html      # macOS
```

### Q: mypy 报告大量错误？

检查是否安装了类型存根：

```bash
pip install types-requests types-setuptools
```

如果第三方库缺少类型，可以在 `pyproject.toml` 中忽略：

```toml
[tool.mypy]
ignore_missing_imports = true
```

### Q: CI 通过但本地失败？

可能原因：
1. Python 版本不同 - 确保使用 3.8
2. 依赖版本不同 - 运行 `pip install -e ".[dev]" --upgrade`
3. 缓存问题 - 清理 `.tox/`、`__pycache__/`、`.pytest_cache/`

---

## 相关文档

- [CI 工作流说明](./zh-CN_ci_workflow.md) - 了解远程 CI 行为
- [代码规范](./zh-CN_code_standards.md) - 代码质量要求
- [开发者入门指南](./zh-CN_developers_guide.md) - 环境配置
