# 课程管理与资料存储实现文档

本文档记录 `feat/file-storage` 分支中课程管理与资料存储功能的实现细节，供后续开发者参考。

---

## 1. 概览

本次新增了三个主要功能：

| 功能 | 说明 |
|------|------|
| 课程管理 | 持久化课程记录，完整 CRUD，支持学期筛选 |
| 资料存储 | 上传/下载/管理课程文件（.pdf/.docx/.pptx/.xlsx/.txt/.md），≤10 MB |
| PDF 预览 | 安全提供 PDF 文件，防路径穿越攻击 |

后端基于 **SQLModel + aiosqlite** 异步 ORM，前端基于 **Pinia + Vue3**。

---

## 2. 数据模型

### 2.1 Course（课程）

`packages/core/src/agent_core/models/course.py`

```python
class Course(SQLModel, table=True):
    id: str = Field(default="", primary_key=True)        # UUID
    name: str                                            # 必填
    code: str = ""                                       # 课程代码，如 CS101
    credits: float | None = None                         # 学分
    instructor: str = ""                                 # 教师
    description: str = ""                               # 课程描述
    tags: str = ""                                       # 标签，逗号分隔
    semester: str = ""                                  # 学期，如 2026Spring
    created_at: datetime | None                         # 创建时间
    updated_at: datetime | None                         # 更新时间
```

### 2.2 CourseMaterial（课程资料）

`packages/core/src/agent_core/models/course_material.py`

```python
class CourseMaterial(SQLModel, table=True):
    id: str = Field(default="", primary_key=True)        # UUID
    course_id: str                                       # 所属课程 ID
    filename: str                                         # 原始文件名
    stored_path: str                                     # 磁盘存储路径（不含根目录前缀）
    file_type: str                                       # 文件扩展名，如 .pdf
    file_size: int                                       # 文件大小（字节）
    description: str = ""                                # 描述
    tags: str = ""                                       # 标签，逗号分隔
    created_at: datetime | None                         # 上传时间
```

物理文件存放于 `{storage_root}/course_materials/{course_id}/{uuid}_{filename}`。

---

## 3. 持久层

### 3.1 CourseStore

`packages/core/src/agent_core/persistence/course_store.py`

使用 SQLModel + aiosqlite 异步引擎。SQLite 数据库文件固定为 `courses.db`，运行时放在 `DB_PATH` 目录下；`DB_PATH` 留空时默认等于 `DATA_PATH`。

**核心方法：**

```python
async def initialize(self)   # 创建异步引擎，建表
async def add(record)        # INSERT 并返回带 ID 的记录
async def list_all(semester) # SELECT，支持学期筛选
async def get(course_id)     # SELECT by PK
async def delete(course_id)  # DELETE by PK
async def update(course_id, fields) # UPDATE 指定字段
```

### 3.2 CourseMaterialStore

`packages/core/src/agent_core/persistence/course_material_store.py`

同样基于 aiosqlite。**关键设计**：删除材料记录时，同时删除磁盘上的物理文件（通过 `os.remove(record.stored_path)`）。

另有工具函数：
- `validate_file_extension(filename)` — 检查扩展名是否在白名单中
- `validate_file_size(size)` — 检查大小是否 ≤10 MB

---

## 4. 服务层

### 4.1 CourseService

`packages/core/src/agent_core/services/course_service.py`

薄封装层，调用 `CourseStore`，异常转换为 `CourseNotFoundError`。

### 4.2 CourseMaterialService

`packages/core/src/agent_core/services/course_material_service.py`

核心业务逻辑：

- **文件路径安全**：`stored_path` 生成逻辑：
  1. 清理文件名中的 `/` `\` `..`，替换非法字符为下划线
  2. 截断到 200 字符
  3. 前缀为 `{material_id}_`（UUID）以避免冲突
  4. 存入 `{material_dir}/{course_id}/`

- **上传流程**：
  1. 验证课程存在（调用 `CourseService.get`）
  2. 验证文件类型和大小
  3. 生成 UUID 和存储路径
  4. 写文件到磁盘
  5. 创建 `CourseMaterial` 记录并持久化

- **删除流程**：调用 `CourseMaterialStore.delete`，store 层同步删除物理文件。

---

## 5. API 层

### 5.1 REST 路由

| 文件 | 前缀 | 说明 |
|------|------|------|
| `routes/courses.py` | `/courses` | Course CRUD |
| `routes/course_materials.py` | `/course-materials` | Material CRUD + 上传/下载 |
| `routes/files.py` | `/pdfs` | 安全 PDF 文件服务 |

**Storage Root 推导逻辑**（`services/course_material_service.py` 中 `resolve_course_material_storage_root`）：

```python
storage_root = Path(cfg.data_path) / "course_materials"
```

REST 上传、Blackboard 下载和课程资料工具均使用同一目录，避免打包运行时依赖进程当前工作目录。

### 5.2 PDF 安全提供

`routes/files.py` 中 `_validate_filename` 实现：

1. URL 解码（`urllib.parse.unquote`）
2. 去除首尾空格
3. 必须是 `.pdf` 扩展名
4. 禁止路径分隔符 `/` `\` 和空字节 `\0`
5. 解析为绝对路径后，检查 `path.is_relative_to(_PDFS_DIR)`（防符号链接穿越）
6. 检查文件存在

### 5.3 级联删除

删除课程时（`routes/courses.py` 的 `delete_course`），先查询该课程所有材料，逐条删除记录（store 层同步删文件），最后删除课程记录。

---

## 6. 前端

### 6.1 API 客户端

`packages/gui/src/api/course.ts`

使用 `fetch` + TypeScript 类型，涵盖所有 Course 和 CourseMaterial 端点。上传使用 `FormData`（ multipart/form-data），直接透传给后端。

### 6.2 Pinia Store

`packages/gui/src/stores/courseStore.ts`

组合式 store（`defineStore` with `setup` style），管理：
- 课程列表 + 当前选中课程 ID
- 当前课程的资料列表
- 加载状态（`isLoadingCourses`、`isLoadingMaterials`、`isUploading`）
- 错误状态

### 6.3 Vue 组件

| 组件 | 说明 |
|------|------|
| `CourseManager.vue` | 课程卡片列表，支持添加/编辑/删除/选中；模态框表单；二次确认删除 |
| `FileManager.vue` | 选中课程后显示；蓝色上传区域含描述/标签字段；文件列表含编辑/下载/删除操作 |

**组件通信**：父组件（如 ChatView）通过 `v-if` 切换 `CourseManager` 和 `FileManager`，选中课程时通过 `select-course` 事件传递课程对象，触发切换。

---

## 7. 测试

| 测试文件 | 覆盖范围 |
|----------|----------|
| `packages/core/tests/test_courses_api.py` | Course 全 CRUD，semester 筛选，级联删除 |
| `packages/core/tests/test_course_materials_api.py` | Material 上传/下载/编辑/删除，文件大小/类型验证，404 处理 |

---

## 8. 已知约束

- **文件存储根目录**：后端根据 `DATA_PATH` 推导，默认写入 `${DATA_PATH}/course_materials/`。
- **文件大小**：硬编码 10 MB 前端检查和后端验证双重保证。
- **并发写入**：同一课程的并发上传使用 UUID 前缀保证文件名不冲突；SQLite 写入本身为串行。
- **无文件类型深度检测**：仅检查扩展名，不验证文件内容 MIME 类型。

---

## 9. 相关文件索引

```
packages/core/src/agent_core/
├── models/
│   ├── course.py              # Course SQLModel + DTO
│   └── course_material.py     # CourseMaterial SQLModel + DTO
├── persistence/
│   ├── course_provider.py        # get_course_store() 单例注入
│   ├── course_store.py            # CourseStore 异步 CRUD
│   ├── course_material_provider.py
│   └── course_material_store.py  # CourseMaterialStore + validate 函数
├── services/
│   ├── course_service.py             # 课程业务逻辑
│   └── course_material_service.py    # 资料业务逻辑（含文件 I/O）
├── api/routes/
│   ├── courses.py              # Course REST 端点
│   ├── course_materials.py     # Material REST 端点
│   └── files.py                # PDF 安全提供
└── tools/
    └── course_tools.py         # AI 工具（analyze_document, generate_quiz, read_course_material）

packages/gui/src/
├── api/course.ts               # API 客户端
├── stores/courseStore.ts      # Pinia store
└── components/widgets/
    ├── CourseManager.vue       # 课程管理 UI
    └── FileManager.vue         # 文件管理 UI
```
