# 开发者指南

本文档为 `deep-solutions` 项目的开发者提供完整的开发环境设置和工作流指南。

## 目录
- [前置条件](#前置条件)
- [获取代码](#获取代码)
- [环境设置](#环境设置)
- [开发工作流](#开发工作流)
- [快速参考](#快速参考)

---

## 前置条件

### 必需工具

| 工具 | 最低版本 | 用途 |
|------|---------|------|
| Python | 3.8+ | 开发必须使用 Python 3.8 |
| Git | 2.0+ | 版本控制 |
| Conda | 最新版 | 环境管理 (推荐) |

### 为什么使用 Python 3.8？

本项目使用 **Python 3.8** 作为开发版本，以确保：
- 与所有目标版本 (3.8-3.12) 的语法兼容性
- 避免使用更高版本的新语法特性
- 保持向后兼容性

---

## 获取代码

### 克隆仓库

```bash
git clone https://github.com/your-org/deep-solutions.git
cd deep-solutions
```

### Fork 工作流（推荐用于贡献者）

1. 在 GitHub 上 Fork 仓库
2. 克隆你的 fork
3. 添加上游远程仓库

```bash
git clone https://github.com/YOUR_USERNAME/deep-solutions.git
cd deep-solutions
git remote add upstream https://github.com/your-org/deep-solutions.git
```

---

## 环境设置

### 方法：Pip-in-Conda（推荐）

此方法将 Conda 环境管理与 pip 包安装相结合：

```bash
# 1. 使用 Python 3.8 创建 Conda 环境
conda create -n deep-solutions python=3.8 -y
conda activate deep-solutions

# 2. 以开发模式安装（包含开发依赖）
pip install -e ".[dev]"

# 3. 安装 pre-commit 钩子
pre-commit install

# 4. 验证安装
python -c "import deep_solutions; print('安装成功！')"
```

### 开发依赖

`pip install -e ".[dev]"` 命令会安装：
- pytest, pytest-cov（测试）
- mypy（类型检查）
- ruff（代码检查和格式化）
- tox（多版本测试）
- pre-commit（Git 钩子）
- commitizen（提交信息）

---

## 开发工作流

### 1. 分支策略

```
main
  └── feature/your-feature-name
  └── fix/bug-description
  └── docs/documentation-update
```

**创建功能分支：**

```bash
# 同步 main 分支
git checkout main
git pull origin main

# 创建功能分支
git checkout -b feature/your-feature-name
```

### 2. 提交更改前

```bash
# 检查代码格式和 lint
ruff format --check src/ tests/
ruff check src/ tests/

# 类型检查
mypy src/

# 运行测试
pytest

# 或运行所有检查
./scripts/check.sh
```

### 3. 提交更改

我们遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

**使用 commitizen（推荐）：**

```bash
cz commit
```

**或手动提交：**

```bash
git add .
git commit -m "feat(core): add xxx features"
```

查看 [提交规范](./zh-CN_commit_conventions.md) 了解格式详情。

### 4. 推送更改

```bash
git push origin feature/your-feature-name
```

### 5. 创建 Pull Request

1. 前往 GitHub 仓库
2. 点击 "New Pull Request"
3. 选择你的功能分支
4. 填写 PR 模板
5. 请求代码审查

### 6. 代码审查流程

- 解决审查意见
- 推送额外提交
- 等待 CI 检查通过
- 获得批准后合并

---

## 快速参考

### 常用命令

| 任务 | 命令 |
|------|------|
| 安装开发依赖 | `pip install -e ".[dev]"` |
| 格式化代码 | `ruff format src/ tests/` |
| Lint 检查 | `ruff check src/ tests/` |
| 类型检查 | `mypy src/` |
| 运行测试 | `pytest` |
| 运行测试（带覆盖率） | `pytest --cov=src` |
| Pre-commit 检查 | `pre-commit run --all-files` |
| 交互式提交 | `cz commit` |

### 开发目录结构

```
deep-solutions/
├── src/                    # 源代码
│   └── deep_solutions/     # 主包
├── tests/                  # 测试文件
├── docs/                   # 文档（英文）
│   └── zh-CN/              # 中文翻译
├── scripts/                # 实用脚本
└── pyproject.toml          # 项目配置
```

---

## 相关文档

- [项目结构](./zh-CN_project_structure.md)
- [代码规范](./zh-CN_code_standards.md)
- [本地测试指南](./zh-CN_local_testing.md)
- [CI 工作流](./zh-CN_ci_workflow.md)
- [提交规范](./zh-CN_commit_conventions.md)
