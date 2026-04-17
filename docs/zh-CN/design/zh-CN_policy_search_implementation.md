# Campus Policy Search（RAG）实现详解

本文档详细说明 `packages/core` 中 Campus Policy Search 的实现原理，包括数据摄取、Embedding、索引构建、检索和 Skill 集成。

---

## 1. 概述

Campus Policy Search 是新增的本地 RAG 能力，用于回答校园政策、培养方案、课程要求、毕业要求等问题。

**相关目录：**

```text
packages/core/src/agent_core/policy_search/
├── build_index.py   # 离线索引构建入口
├── embeddings.py    # Embedding API 封装
├── index.py         # FAISS 索引构建/加载/保存
├── ingest.py        # PDF 解析与切片
├── models.py        # Chunk / Metadata / SearchResult 数据模型
├── patterns.json    # 中文章节标题正则模式
└── retriever.py     # Top-K 检索与结果格式化
```

---

## 2. 数据摄取与切片

**文件：** `packages/core/src/agent_core/policy_search/ingest.py`

`ingest.py` 负责读取 PDF、抽取文本并切分为可检索的文本块。

- PDF 解析：使用 PyMuPDF（`fitz`）
- 切片方式：固定字符窗口 + overlap
- 每个 chunk 绑定元数据：
  - `title`
  - `page`
  - `section`
  - `source_path`
  - `official_url`

这些元数据不是展示用附属信息，而是后续来源确认的基础。

### 2.1 PDF 解析

`parse_pdf()` 使用 `fitz.open()` context manager 确保文件句柄正确关闭。遍历每一页，提取纯文本并记录 1-based 页码。

### 2.2 文本分块

`chunk_text()` 使用滑动窗口将连续文本切分为固定长度 chunk。Overlapping 部分保留上下文。跨页边界时，通过 `buffer_spans` 记录每段文字的页码偏移，精确确定 chunk 归属页。

### 2.3 章节检测

`_detect_section_heading()` 从 `patterns.json` 加载正则模式，匹配中文文档章节标题（如"第一章"、"一、）。

---

## 3. Embedding 与索引

**文件：** `packages/core/src/agent_core/policy_search/embeddings.py`

`embeddings.py` 通过 OpenAI-compatible 接口调用 embedding 模型，当前默认配置为：

- `EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- `EMBEDDING_MODEL=text-embedding-v4`

**文件：** `packages/core/src/agent_core/policy_search/index.py`

`index.py` 使用 `faiss-cpu` 构建本地向量索引，并将产物保存到：

```
packages/core/output/policy_index/
├── index.faiss    # FAISS 向量索引文件
└── chunks.json    # chunk 文本及元数据
```

---

## 4. 检索与格式化

**文件：** `packages/core/src/agent_core/policy_search/retriever.py`

`retriever.py` 的职责是：

1. 将用户问题转换为查询向量
2. 在本地 FAISS 索引中做 Top-K 检索
3. 将检索结果格式化为可直接喂给 LLM 的文本

格式化结果包含：
- 片段正文
- 文档名
- 页码
- 章节
- `[来源 n]` 引用编号

### 4.1 线程安全

retriever 使用模块级单例管理 index 状态（`_index`、`_chunks`、`_index_dir`）。所有读写操作均通过 `threading.Lock()` 保护，避免并发请求在 ThreadPoolExecutor 中出现竞争。

---

## 5. 工具封装

**文件：** `packages/core/src/agent_core/tools/policy_search.py`

暴露 `search_campus_policy(query: str)`，并按统一规范注册到 `ToolRegistry`。

该工具的特点：
- 敏感度为 `ToolSensitivity.SAFE`
- 输入是自然语言问题
- 输出是带引用的检索结果文本
- 当索引不存在时，返回明确错误提示，而不是让模型自由编造

---

## 6. Skill 集成方式

**文件：** `packages/core/src/agent_core/skills/policy_search.py`

系统提示词从 `policy_skill_prompt.json` 加载，对 policy_search skill 做了额外约束：

- 涉及政策/培养方案/课程要求时必须先调用 `search_campus_policy`
- 回答必须基于检索内容
- 关键结论后必须附 `[来源 n]`
- 检索不足时必须明确说明未找到依据

当前 skill 的启用方式是在 API 请求里显式传入 `skill`，例如：

```json
{
  "message": "航空航天工程专业需要多少学分？",
  "skill": "policy_search"
}
```

这意味着当前已完成的是"指定 `policy_search` skill 后的端到端能力"，而不是"通用入口下自动识别问题类型并切换 skill"。

---

## 7. 来源确认机制

当前来源确认依赖 ingest 阶段保存的 chunk metadata，而不是依赖 LLM 自行生成引用。

实现方式：

1. ingest 时给每个 chunk 附加文档元数据
2. 检索命中后保留这些元数据
3. `format_results_for_llm()` 将元数据格式化为 `[来源 n] 文档名 | 第X页 | 章节`
4. skill prompt 要求模型在回答中使用这些来源编号

当前可实现的溯源粒度：
- 文档级
- 页码级
- 部分章节级

尚未实现：
- PDF 内跳页链接
- 条款级精确锚点
- 对回答每一句做自动引用校验

---

## 8. 索引构建脚本

**文件：** `packages/core/src/agent_core/policy_search/build_index.py`

离线 CLI 入口，用于从 PDF 目录构建 FAISS 索引：

```bash
uv run python -m agent_core.policy_search.build_index --pdf-dir ./pdfs --output-dir ./output/policy_index
```

使用前需先构建索引，详见用户指南。

---

## 9. 相关文档

- [用户指南](../user-guide/zh-CN_user_guide.md) — 使用方式与快速开始
- [项目结构](../devs/zh-CN_project_structure.md) — 模块目录说明