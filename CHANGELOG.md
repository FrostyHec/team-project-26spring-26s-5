# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- Course Management (full CRUD — REST API + GUI)
    - `Course` SQLModel table with fields: id, name, code, credits, instructor, description, tags, semester, timestamps
    - `CourseStore` async SQLite persistence (SQLModel + aiosqlite)
    - `CourseService` business logic layer
    - REST endpoints: `GET/POST /courses`, `GET/PATCH/DELETE /courses/{id}`
    - `CourseManager.vue`: card list with add/edit/delete modal, course selection flow into FileManager
    - `courseStore.ts` Pinia store: manages courses + materials state with loading/error tracking
    - `api/course.ts` typed API client for all course and material endpoints
    - Cascade delete: deleting a course removes all its material records and physical files
- Course Material File Storage (upload/download/manage)
    - `CourseMaterial` SQLModel table: id, course_id, filename, stored_path, file_type, file_size, description, tags, created_at
    - `CourseMaterialStore` async SQLite persistence; delete also removes physical file from disk
    - `CourseMaterialService`: validates extension (.pdf/.docx/.pptx/.xlsx/.txt/.md) and size (≤10 MB), generates safe stored paths, handles file I/O
    - REST endpoints: `GET/POST /course-materials`, `GET/PATCH/DELETE /course-materials/{id}`, `GET /course-materials/{id}/download`
    - `FileManager.vue`: upload zone with description/tags fields, file list with download/edit/delete, inline modals
    - File path traversal protection throughout (backend `validate_filename`, frontend size/type guard)
    - File size limit and allowed extensions now configurable via `COURSE_MATERIAL_MAX_SIZE_MB` and `COURSE_MATERIAL_ALLOWED_EXTENSIONS` in `.env` (defaults: 10 MB, `.pdf,.docx,.pptx,.xlsx,.txt,.md`)
- PDF Serving with Path Traversal Protection
    - `GET /pdfs/{filename}` endpoint with `_validate_filename` guard
    - Rejects non-.pdf, path separators, null bytes; resolves path and checks `is_relative_to` pdfs root
    - RFC 5987 UTF-8 encoded Content-Disposition for Chinese filenames
- Course Assistant Skill (AI-powered document analysis + quiz generation)
    - `generate_quiz` tool: validates question JSON, enforces scoring rules (true_false=1pt, multiple_choice=3pt, fill_blank=5pt, short_answer=10pt), difficulty auto-inference, returns `QuizWidgetData`
    - `analyze_document` tool: extracts text from .txt/.md/.pdf/.docx/.pptx/.xlsx, calls evaluation service for summary/key-points/difficult-concepts
    - `read_course_material` tool: fetches file by ID, returns text content for AI processing
    - Prompt engineering: `course_assistant/system_prompt.{en,zh}.md` with structured output format
- GUI Widget Improvements
    - `CourseCardsWidget.vue`: refactored to use new CourseManager component, semester filter support
    - `PolicySearchWidget.vue`: integrated with updated retriever interface
    - `QuizSection.vue`: uses `chatConstants.ts` for session ID management
- i18n: added Chinese and English strings for all new course/file manager components
- Tests: `test_courses_api.py` and `test_course_materials_api.py` covering full CRUD with mocked DB
- Short answer scoring: prompt engineering fixes for evaluation service compatibility
- Policy Search GUI
    - `PolicySearchWidget`: result cards with title, page, section, snippet; copy citation button; PDF preview trigger
    - `PdfViewerWidget`: iframe-based browser-native PDF viewer with pagination (50%-300% zoom), new-tab launch
    - SSE `WidgetDisplayEvent` triggers workspace panel; per-session widget state persistence across tab switches
    - i18n support for all widget strings (Chinese/English)
    - Cleanup: removed dead code (`format_results_for_llm`, `FormattedSource`), unused `pdfjs-dist` dependency and PDF.js CDN scripts
- Quiz: add difficulty field (easy/medium/hard) to questions and quiz sets, auto-inferred from questions, displayed in frontend
- Quiz: fix short_answer scoring when evaluation service unavailable — not counted in total score, shown as unscored

## [0.2.0] - 2025-04-19
- Support Basic Deadline Management Functionalities 
    - import data from blackboard
    - add/edit/delete deadlines
    - deadline display in 3 views (timeline, week, month)
    - Alarming ddls via multiple channels (frontend & email)
- Support Email Agent:
    - Full IMAP/SMTP integration with async I/O (`asyncio.to_thread`), CID inline image rewriting, and attachment deduplication
    - Multi-folder inbox (INBOX / Sent / Starred / Trash / Spam), lazy attachment fetch on demand, and per-attachment download UI
    - Rich-text compose with WangEditor v5; flag actions (mark unread / trash / spam) from detail view
    - Settings panel with fetch period, auto-sync toggle, test connection, and clear cache
    - Security fixes: path traversal guard via `Path.relative_to()`, typed `AttachmentNotFoundError`, correct HTTP 428/404/503 status codes
- Support Basic RAG-based Campus Policy Search
    - PDF Parsing
    - Indexing and context vector storage
    - Related tool implementation
- Support Course Materials Summarization
    - PDF Parsing and reading
    - Quiz Generation
    - New Pannels for summarization display and quiz testing.
- Support settings panel in GUI
    - Configurations of SUSTech Blackboard, Email, Deadline Agent, languages, etc.
- Support i18n (en/zh) switch in frontend
- Project Management:
    - Deprecated Chainlit POC frontend.

## [0.1.0] - 2025-04-01
- Project Initialization:
    - Monorepo project structure with 4 packages (core, cli, poc_frontend, gui)
    - check.sh script for local validation
    - Language check script for source code
    - CI workflow for GitHub Actions
    - Full Chinese documentation
    - Taskfile.yml for task orchestration
- POC Agent Backend:
    - ReAct agent engine using LangGraph StateGraph
    - Tool registry system with decorator-based registration
    - Calculator tools (add, subtract, multiply, divide) for POC demo
    - FastAPI REST API with SSE streaming support
- POC Frontends:
    - CLI frontend with interactive chat and server modes   
    - Chainlit POC frontend with tool call visualization (deprecate in future)
    - Vue3 + TypeScript frontend with Pinia state management and SSE, event support
    - Comprehensive test suite 
