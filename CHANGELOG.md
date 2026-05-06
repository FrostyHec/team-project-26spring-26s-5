# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Session Management
    - Refactor `SessionStore` from hand-written `aiosqlite` CRUD to SQLModel async ORM while preserving API behavior
    - Add provider-aware chat retry flow with `provider_switch` and `failed` stream events enabling graceful fallback
    - Persist discussion-session state: provider preferences, fallback mode, message completion status, manual titles, and recovery from interrupted/failed responses
    - Allow API server to start without enabled LLM provider; chat fails gracefully per-request until configured
    - Implement non-blocking auto-titling for first chat round with separate async LLM request and delayed frontend refresh
    - Persist `debug_mode` with YAML runtime settings for cross-session visibility preferences
    - Add discussion-panel controls: provider/fallback selection, stop-streaming with draft retention, blank-session reuse, inline title editing
    - Surface interrupted/failed assistant states and provider-switch trace steps in chat UI

- Course Management
    - Course CRUD system: REST API (`GET/POST /courses`, `GET/PATCH/DELETE /courses/{id}`) with SQLModel persistence and cascade delete
    - Material upload/download workflow: file validation (.pdf/.docx/.pptx/.xlsx/.txt/.md; 10 MB default), safe path generation, secure I/O
    - Material REST endpoints: `GET/POST /course-materials`, `GET/PATCH/DELETE /course-materials/{id}`, `GET /course-materials/{id}/download`
    - Security: path traversal protection via backend `validate_filename` and frontend guards; RFC 5987 UTF-8 Content-Disposition for Chinese filenames; configurable size/extension limits in `.env`
    - PDF serving: `GET /pdfs/{filename}` endpoint with path validation (rejects non-.pdf, separators, null bytes; enforces `is_relative_to` root)
    - AI-powered Course Assistant: document analysis (`analyze_document`), quiz generation (`generate_quiz` with scoring: true_false=1pt, multiple_choice=3pt, fill_blank=5pt, short_answer=10pt)
    - Quiz improvements: difficulty field (easy/medium/hard) with auto-inference; fixed short-answer scoring when evaluation unavailable

- Policy Search
    - Search UI: `PolicySearchWidget` with result cards (title, page, section, snippet), citation copy, PDF preview
    - PDF viewer: iframe-based browser-native `PdfViewerWidget` with pagination and 50%-300% zoom
    - State management: SSE `WidgetDisplayEvent` triggers workspace panel; per-session widget state persistence
    - Code cleanup: removed dead code, unused `pdfjs-dist` dependency, and PDF.js CDN scripts

- Minors
    - Frontend: Provider settings redesigned as collapsible drag-to-reorder cards; API settings validation with backend error modals; `CourseCardsWidget` (semester filter), `QuizSection` (session ID management)
    - Frontend: Chat input box padding fix; sidebar toggle button added to session management area; removed unused sidebar toggle handler from `ChatView`
    - Chat: split `<think>` reasoning from final answers so GUI trace streams full thinking text while assistant context、CLI output and partial-response persistence stay clean
    - Memory: add file-backed Agent Memory tools with YAML frontmatter, safe `output/agent_memory/` routing, rewrite backups, and focused backend coverage
    - Documentation: refresh database storage docs for SQLModel-based session initialization and backward-compatible schema upgrades
    - Testing: `test_courses_api.py` and `test_course_materials_api.py` covering full CRUD with mocked DB
    - i18n: added Chinese and English strings for course management, file manager, policy search, and settings

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
