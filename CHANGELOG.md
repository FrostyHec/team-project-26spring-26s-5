# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-04-20
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
