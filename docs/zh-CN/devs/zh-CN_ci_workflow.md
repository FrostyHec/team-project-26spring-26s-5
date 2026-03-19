# CI/CD 工作流说明

本文档详细介绍 `deep-solutions` 项目的所有 CI/CD 工作流脚本及其功能。

## 目录
- [工作流概览](#工作流概览)
- [CI 工作流 (ci.yml)](#ci-工作流-ciyml)
- [测试报告工作流 (report.yml)](#测试报告工作流-reportyml)
- [发布工作流](#发布工作流)
- [差异化测试策略](#差异化测试策略)
- [安全模型](#安全模型)
- [性能优化](#性能优化)
- [开发者使用指南](#开发者使用指南)

---

## 工作流概览

项目包含以下 GitHub Actions 工作流：

| 工作流文件 | 名称 | 触发条件 | 用途 |
|------------|------|----------|------|
| `ci.yml` | CI | PR / Push to main | 代码质量检查和测试 |
| `report.yml` | Test Report | CI 完成后 | 发布测试报告到 PR |
| `publish.yml` | Publish to PyPI | 手动触发 | 正式发布到 PyPI |
| `publish-test.yml` | Publish to TestPyPI | 手动触发 | 测试发布到 TestPyPI |

### 架构图

```mermaid
graph TB
  subgraph PR测试 — 快速反馈
    A1[PR 触发]-->A2[Lint + Type Check]
    A2-->A3[Test Python 3.8 only]
    A3-->A4[Build Check]
  end

  subgraph Main分支 — 完整回归
    B1[Push to main]-->B2[Lint + Type Check]
    B2-->B3[Test Python 3.8-3.12 全矩阵]
    B3-->B4[Build Check]
  end

  subgraph 测试报告
    C1[workflow_run 触发]-->C2[下载 artifact]
    C2-->C3[发布 Check Run]
  end
```

---

## CI 工作流 (ci.yml)

### 基本信息

- **文件**: `.github/workflows/ci.yml`
- **触发条件**: Pull Request 或 Push to main
- **权限**: `contents: read`（只读）

### 任务 (Jobs)

#### 1. lint - 代码质量检查

检查代码格式和风格问题。

```yaml
steps:
  - ruff format --check src/ tests/  # 格式检查
  - ruff check src/ tests/           # Lint 检查
```

#### 2. type-check - 类型检查

使用 MyPy 进行静态类型分析。

```yaml
steps:
  - pip install -e ".[dev]"
  - mypy src/
```

#### 3. test - 运行测试

使用 pytest 运行单元测试。

**差异化策略**：
- **PR**: 仅测试 Python 3.8
- **main 分支**: 测试 Python 3.8-3.12 全矩阵

```yaml
strategy:
  matrix:
    python-version: ${{ 
      github.event_name == 'push' && github.ref == 'refs/heads/main' 
      && fromJSON('["3.8", "3.9", "3.10", "3.11", "3.12"]') 
      || fromJSON('["3.8"]') 
    }}
```

**输出产物**：
- `pytest-report.xml` - JUnit 格式测试报告
- `coverage.xml` - 覆盖率报告（仅 Python 3.12）

#### 4. build - 构建检查

验证包可以正常构建。

```yaml
steps:
  - python -m build
  - twine check dist/*
```

---

## 测试报告工作流 (report.yml)

### 基本信息

- **文件**: `.github/workflows/report.yml`
- **触发条件**: CI 工作流完成后
- **权限**: `checks: write`, `pull-requests: write`, `actions: read`

### 功能

1. 下载 CI 生成的测试报告 artifact
2. 使用 `dorny/test-reporter` 发布到 PR
3. 在 PR 界面创建 Check Run，显示测试详情

### 为什么需要单独的报告工作流？

这是 **双 Runner 安全模型** 的一部分：

- **CI 工作流**: 运行来自 fork 的代码，无写权限
- **报告工作流**: 运行在主仓库上下文，有写权限，但只处理静态数据

---

## 发布工作流

### Publish to PyPI (publish.yml)

**用途**: 正式发布到 PyPI

**触发**: 手动触发 (workflow_dispatch)

**流程**:
1. 在所有 Python 版本 (3.8-3.12) 上运行测试
2. 创建 Git Tag
3. 构建 sdist 和 wheel
4. 发布到 PyPI
5. 验证安装
6. 创建 GitHub Release

**前置条件**:
- 配置 `PYPI_API_TOKEN` Secret
- 设置 `pypi` environment

### Publish to TestPyPI (publish-test.yml)

**用途**: 测试发布流程

**触发**: 手动触发 (workflow_dispatch)

**流程**:
1. 创建 Git Tag
2. 构建包
3. 发布到 TestPyPI
4. 验证安装

**前置条件**:
- 配置 `TEST_PYPI_API_TOKEN` Secret
- 设置 `testpypi` environment

---

## 安全模型

本项目采用 **双 Runner 安全模型** 处理 Fork PR 的测试和报告。

### 为什么不用 `pull_request_target`？

`pull_request_target` 虽然可以给 fork PR 写权限，但存在安全风险：

- ❌ Workflow 在 **主仓库上下文** 运行，拥有写权限
- ❌ 如果 checkout PR 代码并执行，可能导致：
  - Secrets 泄露
  - 恶意代码注入
  - Runner 被攻击

### 双 Runner 模型

```
┌─────────────────────────────────────────────────────────────┐
│  Runner A (CI - 测试)                                       │
│  ✅ 执行所有来自 fork 的代码                                │
│  ✅ 无写权限，无 secrets                                    │
│  ✅ 即使被攻破，攻击者也无法窃取机密                        │
│  产出: pytest-report.xml (artifact)                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Runner B (Report - 报告)                                   │
│  ✅ 运行在主仓库上下文，可使用写权限                        │
│  ✅ 只处理静态文件（junit XML）                             │
│  ✅ 不执行 PR 代码，只解析数据                              │
│  产出: PR Check Run                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 性能优化

CI 工作流包含多项性能优化：

### 1. 依赖缓存

使用 `actions/cache@v4` 缓存 pip 包：

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: pip-${{ runner.os }}-${{ hashFiles('**/pyproject.toml') }}
```

### 2. 并行执行

- `lint` 和 `type-check` 并行运行
- 测试矩阵中的不同 Python 版本并行运行

### 3. 自动取消旧任务

同一分支的新 push 会自动取消正在运行的旧任务：

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### 4. 覆盖率优化

覆盖率报告仅在 Python 3.12 上生成，避免重复上传。

---

## 开发者使用指南

### 创建 PR 后

1. **自动触发测试**: CI workflow 自动运行
2. **查看进度**: 在 PR 的 "Checks" 标签页
3. **查看报告**: CI 完成后，Test Report workflow 发布 Check Run
4. **修复问题**: 根据报告修复代码，push 后自动重新触发

### Fork 贡献者

外部贡献者的 PR 会：
- ✅ 自动运行所有测试
- ✅ 获得测试结果反馈（Check Run）
- ✅ 完全安全，无需担心权限问题

### 常见问题

**Q: 为什么我的 PR 只测试 Python 3.8？**

A: 这是差异化测试策略。PR 只测试最小版本以获得快速反馈，合并到 main 后会进行全矩阵测试。

**Q: 测试报告没有出现？**

A: 测试报告由单独的 workflow 生成，需要等待 CI 完成后几分钟。

**Q: CI 缓存没有命中？**

A: 当 `pyproject.toml` 变化时缓存会失效。这是正常行为，确保使用正确的依赖版本。

---

## 相关文档

- [本地测试指南](./zh-CN_local_testing.md) - 在本地运行 CI 检查
- [发布指南](./zh-CN_publishing.md) - 发布到 PyPI
- [代码规范](./zh-CN_code_standards.md) - PR 合并要求
