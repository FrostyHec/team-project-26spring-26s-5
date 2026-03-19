# Agent 开发指南

本指南为 AI 代理（及开发者）提供了关于 `deep-solutions` 项目的完整贡献和维护信息。

## 目录
1. [项目工程结构](#项目工程结构)
2. [代码格式与开发规范](#代码格式与开发规范)
3. [本地测试指南](#本地测试指南)
4. [维护与发布指南](#维护与发布指南)

---

## 项目工程结构

### 0. 目录布局

```
deep-solutions/
├── src/deep_solutions/       # 主要包源代码
├── tests/                    # 单元测试
├── docs/                     # 文档（双语）
│   ├── en-US/                # 英文文档（devs/、user-guide/、design/）
│   └── zh-CN/                # 中文文档（与 en-US 结构一致）
├── scripts/                  # 开发与发布脚本
├── .github/                  # GitHub 配置（工作流、模板、dependabot）
├── pyproject.toml            # 项目元数据与工具配置
├── environment.yml           # Conda 环境规范
├── tox.ini                   # Tox 多版本测试配置
├── README.md                 # 英文 README
├── README.zh-CN.md           # 中文 README
└── CHANGELOG.md              # 发布历史
```

| 目录 | 用途 |
|-----|------|
| `src/deep_solutions/` | 主要包模块（core、utils 等） |
| `tests/` | pytest 单元测试 |
| `docs/en-US/` | 英文文档（devs/、user-guide/、design/） |
| `docs/zh-CN/` | 中文文档（与 en-US/ 结构镜像） |
| `scripts/` | 开发脚本：`check.sh`、`ci-local.sh`、`check_language.py`、`document_checker.py`、`test_release.sh`、`final_release.sh` |
| `.github/workflows/` | GitHub Actions：CI、发布、测试报告 |
| `.github/ISSUE_TEMPLATE/` | Issue 模板（bug、功能、文档、自定义） |
| `pyproject.toml` | 项目配置：依赖、工具设置（ruff、mypy、pytest） |
| `environment.yml` | Conda 环境文件用于开发设置 |
| `tox.ini` | 多 Python 版本测试（3.8-3.12） |

### 0.1. 包分布：`src/deep_solutions/`

```
src/deep_solutions/
├── __init__.py               # 公开 API：hello_world、DeepSolution、format_output、get_library_version
├── _version.py               # setuptools-scm 自动生成（勿编辑）
├── tools/                    # 面向用户的工具集（公开 API）
│   ├── helloworld/           # 模板/示例工具
│   │   ├── core.py           # 核心功能（@public_api）
│   │   ├── utils.py          # 工具函数（@public_api）
│   │   └── __init__.py       # 公开 API 导出
│   └── parameter_search/     # 参数搜索库
│       ├── core/             # 核心引擎（ParamSearcher、SearchResult）
│       ├── epochs/           # 内置 epoch 实现（timed_epoch、simple_epoch）
│       ├── analyzers/        # 结果分析器（BestParamAnalyzer、ChartAnalyzer）
│       └── pytorch/          # PyTorch 封装（DataLoaderParamSelector）
└── _utils/                   # 内部工具（非公开 API）
    ├── timer.py              # 性能计时
    ├── metrics.py            # 指标收集
    ├── decorators.py         # @public_api 装饰器
    └── __init__.py           # 内部导出
```

**结构原则**：
- **`tools/`**: 面向用户的工具（公开 API）。每个工具都是完整的、面向任务的包。使用 `@public_api` 装饰器标记稳定 API。
- **`_utils/`**: 内部的、项目无关的工具。非公开 API。用户不应从 `_utils` 导入。
- **测试**: 在 `tests/test_tools/` 和 `tests/test__utils/` 下匹配结构。

| 模块 | 内容 | 用途 |
|-----|------|------|
| `tools/helloworld/` | `hello_world()`、`DeepSolution`、`format_output()` | 演示结构的模板工具 |
| `tools/parameter_search/` | `ParamSearcher`、`DataLoaderParamSelector` | 参数空间探索 |
| `_utils/` | `Timer`、`MetricsCollector`、`@public_api` | 所有模块的内部工具 |

---

### 0.2. 开发环境

#### 项目概览

- **语言**: Python 3.8+（最小：3.8，最大测试：3.13）
- **包管理器**: Conda + pip
- **构建系统**: setuptools 配合 setuptools-scm（从 Git 标签自动版本控制）
- **代码质量**: Ruff（格式+检查）、mypy（类型检查）、pytest（测试）
- **CI/CD**: GitHub Actions（CI、发布、测试报告）

#### 依赖信息

**核心依赖**（运行时）：
```
numpy >= 1.17.0
scipy >= 1.5.0
```

**开发依赖**（可选）：
```
pytest >= 7.0.0          # 单元测试
pytest-cov >= 4.0.0      # 覆盖率报告
ruff >= 0.4.0            # 格式化 + 检查
mypy >= 1.0.0            # 类型检查
build >= 0.10.0          # 构建包
twine >= 4.0.0           # 发布到 PyPI
tox >= 4.0.0             # 多版本测试
commitizen >= 3.0.0      # 约定式提交
pre-commit >= 3.0.0      # Git hooks
```

#### 开发环境搭建

**第 1 步：克隆仓库**
```bash
git clone https://github.com/FrostyHec/deep-solutions.git
cd deep-solutions
```

**第 2 步：创建 Conda 环境**
```bash
conda env create -f environment.yml
conda activate deep-solutions
```

**第 3 步：以可编辑模式安装包**
```bash
pip install -e ".[dev]"
```

**第 4 步：验证设置**
```bash
python -c "import deep_solutions; print(f'Version: {deep_solutions.__version__}')"
python -m pytest tests/ -v
```

#### 依赖管理

**核心原则**：所有 pip 依赖只在 `pyproject.toml` 中管理。
- 运行时依赖 → `[project].dependencies`
- 开发依赖 → `[project.optional-dependencies].dev`
- 本地开发环境必须严格等同于 `pyproject.toml` 环境

**更新策略**：
- **运行时依赖**：谨慎更新（影响用户）。仅在需要新功能时提高最小版本。
- **开发依赖**：可以更积极更新（仅影响贡献者和 CI）。

**新增依赖：**

1. 创建分支：`git checkout -b chore/add-<pkg>`
2. 编辑 `pyproject.toml`（添加版本如 `"package>=x.y"`）
3. 重新安装：`pip install -U pip && pip install -e ".[dev]"`
4. 验证：`bash scripts/check.sh && tox`
5. 提交（说明原因，如 `"build(deps): add requests for HTTP support"`）

**升级已有依赖：**

当需要新版本的新特性（从版本 X.Y 开始可用）时：
1. 更新 `pyproject.toml`：改为 `>=x.y`
2. 重新安装：`pip install -U pip && pip install -e ".[dev]"`
3. 验证：`bash scripts/check.sh && tox`

示例：
```
# 修改前: numpy>=1.17
# 修改后（需要新 API）: numpy>=1.23
```

**验证清单**（任何依赖改动后必须做）：
- [ ] `pip install -e ".[dev]"` 成功
- [ ] `bash scripts/check.sh` 通过
- [ ] `tox` 通过（至少 Python 3.8 + 最新版本）

---

## 代码格式与开发规范

### 语言政策

- **源代码**: 仅英文（不允许中文）
  - 注释、文档字符串、变量名必须为英文
  - 函数参数和返回值需要类型提示

- **文档**: 双语（英文基础 + 中文翻译）
  - 英文文档位于 `docs/en-US/`（按 devs/、user-guide/、design/ 组织）
  - 中文文档位于 `docs/zh-CN/`（与 en-US/ 结构镜像）
  - 详见 [语言指南](zh-CN_language_guidelines.md)

- **Git 提交**: 仅英文（约定式提交格式）
  - 格式：`type(scope): subject`（例如 `feat(core): add new solver`）
  - 详见 [提交约定](zh-CN_commit_conventions.md)

### 代码风格与标准

**格式化**（Ruff）：
- 行长：88 字符
- 引号风格：双引号（`"`）
- 缩进：4 个空格

**检查**（Ruff）：
- 无未使用的导入
- PEP 8 兼容
- 启用 Bugbear 检查
- 启用推导式检查

**类型提示**（mypy）：
- 所有公开函数必须提供
- 目标 Python 3.8 兼容性
- 示例：
  ```python
  def process_data(x: List[int]) -> Dict[str, float]:
      """处理整数列表。"""
      return {"mean": sum(x) / len(x)}
  ```

**文档字符串**：
- 使用 Google 风格文档字符串
- 包含 Args、Returns、Raises 部分
- 示例：
  ```python
  def hello_world() -> str:
      """返回问候信息。
      
      返回:
          一个简单的问候字符串。
      """
      return "Hello from deep-solutions!"
  ```

### 何时允许使用中文

✅ **允许**：
- `docs/zh-CN/` 目录中的文档（文件以 `zh-CN_` 为前缀）
- 中文文档文件中的注释
- 面向用户的错误消息（可本地化），但需要使用适当的 i18n 框架

❌ **不允许**：
- 源代码（`.py` 文件）
- Git 提交消息
- GitHub Issue/PR 标题
- 代码注释

---

## 本地测试指南

### 一键运行所有检查

```bash
# 使用 bash 脚本
bash scripts/check.sh

# 或手动按顺序运行：
ruff format --check src/ tests/     # 1. 格式检查
ruff check src/ tests/               # 2. 检查代码质量
mypy src/                            # 3. 类型检查
python scripts/check_language.py     # 4. 语言检查
pytest                               # 5. 单元测试
```

### 运行单元测试

```bash
# 运行所有测试并生成覆盖率
pytest

# 运行特定测试文件
pytest tests/test_core.py

# 详细输出
pytest -v

# 运行匹配模式的测试
pytest -k "test_hello" -v
```

### 运行代码格式检查（Ruff）

```bash
# 检查格式
ruff format --check src/ tests/

# 自动修复格式
ruff format src/ tests/

# 检查代码质量
ruff check src/ tests/

# 自动修复检查问题
ruff check --fix src/ tests/
```

### 运行类型检查（mypy）

```bash
# 类型检查
mypy src/

# 详细类型检查输出
mypy src/ --show-error-codes
```

### 运行语言检查

```bash
# 检查源代码中的中文字符
python scripts/check_language.py -v
```

### 多版本测试（tox）

对多个 Python 版本进行测试（3.8-3.12）：

```bash
# 运行所有 Python 版本
tox

# 运行特定 Python 版本
tox -e py38

# 运行并生成覆盖率报告
tox -- --cov=deep_solutions
```

### 覆盖率报告

查看测试覆盖率：
```bash
pytest --cov=deep_solutions --cov-report=html
# 在浏览器中打开 htmlcov/index.html
```

---

## 维护与发布指南

### 版本管理

项目使用 **setuptools-scm** 从 Git 标签自动生成版本。

**版本格式**：`v<major>.<minor>.<patch>`（例如 `v1.0.0`、`v0.2.1`）

### 发布清单

**前置要求**（一次性设置）：
```bash
conda install -c conda-forge gh
gh auth login
```

#### 标准发布流程（推荐）

以发布 `v0.1.1` 为例：

**步骤 A — 在 TestPyPI 上测试** (`test_release.sh`)：
```bash
bash scripts/test_release.sh
# 输入标签：v0.1.1.dev1
# 如果失败，修复后使用 v0.1.1.dev2 重新运行，以此类推
```

**步骤 B — 发布到 PyPI** (`final_release.sh`)：
```bash
bash scripts/final_release.sh
# 选择更名模式 (y)：将 v0.1.1.dev1 更名为 v0.1.1
# 可选择清理其他 .dev 标签
# 脚本触发 publish.yml 并等待结果
```

> **快捷方式**：如果有信心，可以在步骤 A 中直接使用 `v0.1.1` 进行测试
> （不加 `.dev` 后缀），然后在步骤 B 中使用直接模式 (n)。

#### `test_release.sh` — 测试发布

自动化 TestPyPI 验证流程：
1. 提醒更新 CHANGELOG.md
2. 切换到 main 分支并拉取最新代码
3. 提示输入版本标签（例如 `v0.1.1.dev1`）
4. 创建并推送 git 标签
5. 通过 gh CLI 触发 `publish-test.yml`
6. 等待完成并显示结果

#### `final_release.sh` — 正式发布

发布到生产环境 PyPI，支持两种模式：

- **更名模式**（常用）：将测试标签更名为正式版本
  （例如 `v0.1.1.dev3` → `v0.1.1`），可选删除剩余 `.dev` 标签。
- **直接模式**：直接使用已有标签（当你直接用最终版本号测试时）。

然后触发 `publish.yml`，等待完成并报告结果。

### CI 工作流

| 工作流 | 触发条件 | 用途 |
|-------|--------|------|
| `CI` | PR / 推送到 main | 检查、类型检查、测试（PR 仅 3.8，main 完整矩阵） |
| `Test Report` | CI 完成后 | 解析测试结果，在 PR 中发布粘性注释 |
| `Publish to TestPyPI` | 手动分发 | 构建并发布到 TestPyPI 进行测试 |
| `Publish to PyPI` | 手动分发 | 构建并发布到生产 PyPI，创建 Release |

### 常用命令参考

| 命令 | 用途 |
|-----|------|
| `conda activate deep-solutions` | 激活开发环境 |
| `pip install -e ".[dev]"` | 以可编辑模式安装包（含开发依赖） |
| `bash scripts/check.sh` | 运行所有本地检查（格式、检查、类型、语言、测试） |
| `bash scripts/ci-local.sh` | 本地模拟 CI 管道 |
| `python scripts/check_language.py` | 检查代码纯英文（调用 document_checker） |
| `python scripts/document_checker.py` | 检查双语文档、空引用、文档结构 |
| `pytest` | 运行单元测试 |
| `ruff format src/ tests/` | 自动修复代码格式 |
| `ruff check --fix src/ tests/` | 自动修复检查问题 |
| `mypy src/` | 类型检查 |
| `tox` | 在 Python 3.8-3.12 上测试 |
| `git tag -a v1.0.0 -m "Release v1.0.0"` | 创建发布标签 |
| `python -m build` | 构建分发（wheel + sdist） |
| `twine upload dist/*` | 上传到 PyPI |

---

## 文档与结构同步

当项目文件结构发生重大变更时，以下文档**必须**同步更新：

| 文档 | 更新内容 |
|------|----------|
| `en-US_project_structure.md` + `zh-CN_project_structure.md` | 目录树、文件描述 |
| `en-US_agent.md` + `zh-CN_agent.md` | 目录布局（§0）、脚本表 |
| `docs/{en-US,zh-CN}/index.md` | 新增子目录时更新顶级索引 |
| `docs/{en-US,zh-CN}/{subdir}/index.md` | 文件增删时更新子目录索引 |
| `README.md` + `README.zh-CN.md` | 文档链接表 |

### 文档文件命名约定

- 英文文档：`docs/en-US/{subdir}/en-US_filename.md`
- 中文文档：`docs/zh-CN/{subdir}/zh-CN_filename.md`
- 每个新文档必须同时有 EN 和 ZH 版本
- 每个目录必须包含 `index.md`
- `check_language.py` 自动检查双语对齐

---

## 其他资源

- **[开发者指南](zh-CN_developers_guide.md)** - 详细的设置和贡献工作流
- **[代码标准](zh-CN_code_standards.md)** - PR 工作流、合并要求
- **[提交约定](zh-CN_commit_conventions.md)** - 约定式提交格式
- **[项目结构](zh-CN_project_structure.md)** - 依赖管理详情
- **[CI 工作流](zh-CN_ci_workflow.md)** - GitHub Actions 管道详情
- **[本地测试](zh-CN_local_testing.md)** - 综合测试指南
- **[发布指南](zh-CN_publishing.md)** - 发布流程深潜
- **[语言指南](zh-CN_language_guidelines.md)** - 语言政策

