# 项目结构说明

本文档简要介绍 `deep-solutions` 项目的目录结构、依赖管理和开发环境要求。

## 目录
- [目录结构](#目录结构)
- [依赖管理](#依赖管理)
- [Python 版本要求](#python-版本要求)
- [配置文件说明](#配置文件说明)

---

## 目录结构

```
deep-solutions/
├── src/deep_solutions/          # 主包（src-layout 布局）
│   ├── __init__.py              # 公共 API 导出
│   ├── _version.py              # setuptools-scm 自动生成
│   ├── tools/                   # 面向用户的工具集（公共 API）
│   │   ├── helloworld/          # 模板/示例工具
│   │   │   ├── core.py          # 核心功能（@public_api 标记）
│   │   │   ├── utils.py         # 工具函数（@public_api 标记）
│   │   │   └── __init__.py      # 公共 API 导出
│   │   └── parameter_search/    # 参数搜索库
│   │       ├── core/            # 核心引擎（ParamSearcher）
│   │       ├── epochs/          # 内置 epoch 实现
│   │       ├── analyzers/       # 结果分析器（图表、最佳参数）
│   │       └── pytorch/         # PyTorch DataLoader 封装
│   └── _utils/                  # 内部工具（非公共 API）
│       ├── timer.py             # 性能计时工具
│       ├── metrics.py           # 指标收集
│       ├── decorators.py        # @public_api 装饰器
│       └── __init__.py          # 内部导出
│
├── tests/                       # 单元测试（pytest）
│   ├── __init__.py
│   ├── test_tools/              # 面向用户工具的测试
│   │   ├── test_helloworld.py   # helloworld 工具测试
│   │   └── test_parameter_search/  # 参数搜索测试
│   └── test__utils/             # 内部工具的测试
│       └── test_utils.py        # timer、metrics、decorators 测试
│
├── poc/                         # 概念验证示例
│   └── param_selector/          # 参数选择 POC
│       └── dataloader_param_selector.py  # 可运行的 DataLoader 示例
│
├── docs/                        # 文档（双语）
│   ├── en-US/                   # 英文文档
│   │   ├── devs/                # 开发指南（配置、规范、CI、发布）
│   │   ├── user-guide/          # 用户教程和使用说明
│   │   ├── design/              # 架构和设计文档
│   │   └── index.md             # EN 文档索引
│   └── zh-CN/                   # 中文文档（与 en-US 结构一致）
│       ├── devs/                # 开发指南
│       ├── user-guide/          # 用户指南
│       ├── design/              # 设计文档
│       └── index.md             # ZH 文档索引
│
├── scripts/                     # 开发与发布脚本
│   ├── check.sh                 # 运行所有本地检查（格式、lint、类型、语言、测试）
│   ├── ci-local.sh              # 本地模拟完整 CI 流程
│   ├── check_language.py        # 验证代码纯英文（调用 document_checker）
│   ├── document_checker.py      # 检查双语文档、空引用、文档结构
│   ├── test_release.sh          # 自动化 TestPyPI 测试发布
│   └── final_release.sh         # 自动化正式 PyPI 发布
│
├── .github/                     # GitHub 配置
│   ├── dependabot.yml           # Dependabot 依赖更新配置
│   ├── PULL_REQUEST_TEMPLATE.md # PR 描述模板
│   ├── ISSUE_TEMPLATE/          # Issue 模板
│   │   ├── config.yml           # 模板选择器配置
│   │   ├── bug_report.md        # Bug 报告模板
│   │   ├── feature_request.md   # 功能请求模板
│   │   ├── documentation.md     # 文档问题模板
│   │   └── custom.md            # 自定义 Issue 模板
│   └── workflows/               # GitHub Actions 工作流
│       ├── ci.yml               # CI：lint、类型检查、测试
│       ├── report.yml           # 发布测试结果到 PR 评论
│       ├── publish-test.yml     # 发布到 TestPyPI + 验证
│       └── publish.yml          # 发布到 PyPI + 创建 GitHub Release
│
├── pyproject.toml               # 项目元数据、依赖、工具配置
├── tox.ini                      # 多 Python 版本测试（3.8-3.12）
├── environment.yml              # Conda 环境（仅 Python 版本）
├── .pre-commit-config.yaml      # Pre-commit hooks 配置
├── .gitmessage                  # Git 提交消息模板
├── .gitignore                   # Git 忽略规则
├── README.md                    # 项目说明（英文）
├── README.zh-CN.md              # 项目说明（中文）
├── CHANGELOG.md                 # 发布历史
└── LICENSE                      # Apache 2.0 许可证
```

### 核心结构原则

**tools/ vs _utils/**: 代码库区分面向用户的工具和内部工具：

- **`tools/`**: 面向用户的工具，属于公共 API 的一部分。每个工具都是一个完整的、面向任务的包，用户可以直接导入和使用。示例：`helloworld`、`parameter_search`。
- **`_utils/`**: 内部的、项目无关的工具代码，在代码库中跨模块使用。NOT 公共 API 的一部分。用户不应直接从 `_utils` 导入。示例：`Timer`、`MetricsCollector`、`@public_api` 装饰器。

**@public_api 装饰器**: 使用 `@public_api` 装饰的函数和类被明确标记为稳定的公共 API。该装饰器：
- 在文档字符串前添加 `[PUBLIC API]` 标记以提高可见性
- 向用户和开发者表明该 API 是稳定且受支持的
- 用于 `tools/` 模块中标记面向用户的功能
- 示例：`@public_api\ndef hello_world() -> str: ...`

---

## 依赖管理

### 依赖策略：Pip-in-Conda

- **Conda**：仅管理 Python 版本和 pip（`environment.yml`）
- **pip / pyproject.toml**：管理所有包依赖
- 确保开发和生产依赖保持同步

### 依赖分类（`pyproject.toml`）

| 类别 | 配置节 | 用途 |
|------|--------|------|
| 核心 | `[project] dependencies` | 运行时需求（numpy、scipy、torch、matplotlib） |
| 开发 | `[project.optional-dependencies] dev` | 测试、检查、格式化、构建工具 |
| 文档 | `[project.optional-dependencies] docs` | Sphinx 文档构建 |

### 核心依赖

以下依赖对所有用户都是必需的，会自动安装：

- **NumPy** (>=1.17.0): 数值计算基础
- **SciPy** (>=1.5.0): 科学计算算法
- **PyTorch** (>=1.7.0): 深度学习框架（参数搜索工具所需）
- **Matplotlib** (>=3.3.0): 可视化和绘图（图表生成所需）

这些在 `pyproject.toml` 的 `[project] dependencies` 中定义。

### 安装方式

```bash
# 仅安装核心依赖
pip install .

# 核心 + 开发依赖（推荐开发时使用）
pip install -e ".[dev]"

# 安装所有
pip install -e ".[dev,docs]"
```

### 添加依赖

1. 在 `pyproject.toml` 中的相应部分添加
2. 重新安装：`pip install -e ".[dev]"`

> **注意**：不要在 `environment.yml` 中添加 Python 包——它仅管理 Python 版本。

---

## Python 版本要求

| Python 版本 | 状态 |
|-------------|------|
| 3.8 | ✅ 支持（**开发版本**） |
| 3.9–3.12 | ✅ 支持 |

### ⚠️ 开发必须使用 Python 3.8

Python 3.8 是最低支持版本。在 3.8 下开发保证向上兼容，避免意外使用新语法（`match-case`、`X | Y` 类型联合等）。

```bash
conda create -n deep-solutions python=3.8 -y
conda activate deep-solutions
pip install -e ".[dev]"
```

---

## 配置文件说明

| 文件 | 用途 |
|------|------|
| `pyproject.toml` | 项目元数据、依赖、工具配置（ruff、pytest、mypy、commitizen、setuptools-scm） |
| `tox.ini` | 多版本测试（Python 3.8–3.12） |
| `environment.yml` | Conda 环境规范（仅 Python 版本） |
| `.pre-commit-config.yaml` | Pre-commit hooks 代码质量检查 |
| `.gitmessage` | Git 提交消息模板 |

---

## 版本管理

项目使用 **setuptools-scm** 从 Git 标签自动生成版本号：

- **标签格式**：`v<MAJOR>.<MINOR>.<PATCH>`（例如 `v1.0.0`）
- **自动生成**：`src/deep_solutions/_version.py`
- **遵循**：[语义化版本](https://semver.org/)

---

## 相关文档

- [开发者入门指南](zh-CN_developers_guide.md)
- [代码规范](zh-CN_code_standards.md)
- [本地测试指南](zh-CN_local_testing.md)
