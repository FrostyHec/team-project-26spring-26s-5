# 语言规范

## 概述

本项目采用双语策略：

- **源代码**（`.py`、`.ts`、`.vue`、`.js`）：**仅限英文**
- **文档**（`.md`）：中文为主
- **Commit Messages**：英文

## 源代码要求

所有源代码文件中的以下内容必须使用英文：

- 变量名、函数名、类名
- 注释
- 文档字符串
- 字符串常量（除非是面向用户的显示文本）
- 错误信息

### 正确示例

```python
# Good: English comments and docstrings
def calculate_sum(a: float, b: float) -> float:
    """Calculate the sum of two numbers."""
    return a + b
```

### 错误示例

```python
# Bad: Chinese comments
def calculate_sum(a: float, b: float) -> float:
    """计算两个数字的和。"""  # ← 不允许
    return a + b
```

## 强制执行

### check_language.py

`scripts/check_language.py` 会扫描 `packages/` 目录下的所有源代码文件，检查是否包含中文字符。

```bash
# 手动运行
python3 scripts/check_language.py --root .

# 作为 check.sh 的一部分自动运行
bash scripts/check.sh
```

### 检查范围

| 目录 | 文件类型 | 检查内容 |
|------|----------|----------|
| `packages/` | `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.vue` | 中文字符 |
| `.github/` | `.yml`, `.yaml` | 中文字符 |
| `scripts/` | `.py`, `.sh` | 中文字符 |

### 排除目录

以下目录不在检查范围内：

- `node_modules/`
- `.venv/`
- `__pycache__/`
- `.git/`
- `dist/`
- `build/`
