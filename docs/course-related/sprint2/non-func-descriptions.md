# Non-Functional Features

This section documents the engineering efforts invested in improving the non-functional qualities of the system, covering performance, security, reliability, user experience, maintainability, and deployment portability.

---

## 1. Performance and Responsiveness

### Async Backend and Non-blocking I/O

The backend is built on **FastAPI** with pervasive use of async APIs. Blocking operations are explicitly offloaded to avoid stalling the event loop:

- Blocking IMAP/SMTP calls in `email_client.py` are wrapped in `asyncio.to_thread()`, so email synchronisation, sending, and attachment downloads do not block the FastAPI event loop.
- The tool registry in `tools/registry.py` distinguishes between async and sync tool functions; synchronous tools are dispatched through an executor, keeping the Agent loop non-blocking.
- Core data stores (`persistence/*_store.py`) use `aiosqlite` or SQLAlchemy async engine for session, email, deadline, and news push operations.

### Streaming Chat Responses

The chat interface delivers responses via **Server-Sent Events (SSE)**:

- The `/chat/stream` endpoint returns a `StreamingResponse` with `media_type="text/event-stream"`.
- The Agent engine (`engine/agent.py`) converts LangGraph events into typed protocol events — `TOKEN`, `THINKING`, `TOOL_START`, `TOOL_END`, `APPROVAL_REQUEST`, `WIDGET_DISPLAY`, etc.
- The Vue frontend (`api/agent.ts`) reads the stream incrementally using `ReadableStream.getReader()`, and the chat store appends tokens to the assistant message in real time.
- Users can interrupt an ongoing stream; partial output is preserved on both client and server.

This eliminates the need to wait for a complete LLM response before seeing any output, significantly reducing perceived latency.

### Policy Search with FAISS Vector Index

Campus policy retrieval uses an **offline-built FAISS vector index** rather than re-parsing PDFs on every query:

- `policy_search/build_index.py` extracts text from PDFs, splits it into fixed-size chunks with overlap, generates embeddings, and persists the index.
- The retriever (`policy_search/retriever.py`) uses a module-level singleton with lazy loading and a `threading.Lock`, so the index is loaded once and reused across all queries.
- At query time, only a single embedding call and a top-K vector search are needed.

### Email Caching and Lazy Fetch

The email module applies a multi-layer caching strategy:

- `sync_emails()` only synchronises message summaries and attachment metadata.
- Full HTML body and attachment content are fetched lazily via `ensure_email_content_fetched()`, only when the user opens a message. If `content_fetched=True`, the local cache is returned immediately.
- `download_attachment()` returns the local record directly for already-downloaded attachments.
- The Vue email store (`stores/email.ts`) maintains a `folderCache`, displaying cached folder contents immediately while refreshing in the background.
- A `downloadingAtts: Set<number>` guard prevents duplicate attachment download requests.

### News Push: Prepare-then-Dispatch

The campus news push pipeline separates slow LLM report generation from the actual send time:

- `news_push_service.py` runs a **Prepare** phase 5 minutes before the scheduled push time, generating the daily digest and caching it in the `news_push_prepared` table.
- The **Dispatch** phase reads the cached report and sends the email, typically performing only an SMTP call at the scheduled moment.
- If the prepare window was missed at startup, the digest is generated inline during the dispatch tick.

This removes the 30–90 second LLM generation delay from the user-visible send time.

### Frontend Build Optimisation

- `vite.config.ts` enables Vue DevTools only in non-test environments, preventing development plugins from affecting test builds.
- `optimizeDeps.include = ['@wangeditor/editor']` pre-bundles the rich text editor dependency to avoid resolution issues.
- The `Dockerfile` uses a **multi-stage build**: the GUI is compiled in a Node builder stage, and only the static `dist/` output is copied into the Python runtime image, keeping the production image free of frontend build tooling.

---

## 2. Security and Privacy

### Credentials Encrypted at Rest

User CAS and email passwords are never stored in plaintext:

- `security/encryption.py` implements symmetric encryption using `cryptography.fernet.Fernet`. The encryption key is loaded from the `SETTINGS_ENCRYPTION_KEY` environment variable or auto-generated and persisted at `DATA_PATH/.encryption_key`.
- `persistence/profile_store.py` encrypts passwords on write and decrypts them only when needed internally by services.
- The settings API (`api/routes/settings.py`) returns only `*_password_is_set` boolean flags — no ciphertext or plaintext password is ever included in API responses.

### Path Traversal and Filename Sanitisation

File access and upload paths are hardened at multiple points:

- The PDF serving endpoint (`api/routes/files.py`) rejects filenames containing `/`, `\`, or null bytes, and uses `Path.resolve()` with `is_relative_to()` to confirm the resolved path remains within the designated PDF directory.
- `services/course_material_service.py` strips `/`, `\`, `..`, illegal characters, hidden filenames, and overly long names from uploaded files, generating unique paths for name collisions.
- `services/email_client.py` sanitises attachment filenames with `pathvalidate.sanitize_filename()` and validates the resolved write path against the attachment directory before saving.
- Path traversal behaviour is covered by tests in `tests/test_email.py`.

### Upload Limits and Type Validation

Course material uploads enforce both file type and size constraints:

- Only `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.txt`, and `.md` are accepted (default limit: 10 MB).
- `services/course_material_service.py` applies `validate_file_extension()` and `validate_file_size()` before processing any upload.
- Limits are configurable via `COURSE_MATERIAL_MAX_SIZE_MB` and `COURSE_MATERIAL_ALLOWED_EXTENSIONS` in `config.py`.

### Human-in-the-Loop Approval for Sensitive Tools

The Agent tool system requires explicit user approval before executing sensitive operations:

- Tools are classified as `ToolSensitivity.SAFE` or `ToolSensitivity.SENSITIVE` in `tools/registry.py`.
- Before executing a sensitive tool, the Agent emits an `APPROVAL_REQUEST` event. If the user rejects or the request times out (120 seconds), the tool is not executed and a cancellation message is returned.
- `api/approval.py` manages pending approvals using `asyncio.Event`.
- The Vue component `ChatApprovalBanner.vue` presents the tool name and parameters to the user, who must explicitly click **Approve** or **Reject**.
- This behaviour is covered by `tests/test_hitl.py`, `test_approval.py`, and `test_registry.py`.

### Safe Rendering in the Frontend

Rich content from external sources is isolated before rendering:

- `ChatMessageBubble.vue` renders LLM output through **MarkdownIt** and then sanitises the result with **DOMPurify** before binding via `v-html`, mitigating XSS risks.
- `InboxWidget.vue` renders email HTML bodies inside an `<iframe sandbox="allow-same-origin">`, preventing injected scripts from accessing the main application context.
- `WebPreviewWidget.vue` similarly uses a sandboxed iframe for external web page previews.

### Secret-safe Logging

- `email_client.py` masks the local part of email account addresses via `_mask_account_for_log()` before writing to logs.
- Connection failure logs record host, port, masked account, and exception type — never the password.
- A test in `tests/test_email.py` explicitly asserts that passwords do not appear in failure log output.

### Secure Electron Shell Defaults

The desktop application disables high-risk Electron capabilities by default:

- `packages/desktop/src/main.ts` creates the browser window with `contextIsolation: true` and `nodeIntegration: false`, preventing renderer-side code from accessing Node.js APIs directly.
- `APP_PORT` is validated to be an integer in the range 1–65535 in `src/env.ts`.
- The desktop backend manager polls `/api/health` for up to 30 seconds before loading the UI; if the backend fails to start, an error dialog is shown and the application exits cleanly.

---

## 3. Reliability and Fault Tolerance

### Health Check and Startup Verification

- `api/routes/health.py` exposes a `/health` endpoint returning `{"status": "ok"}`.
- The `Dockerfile` configures a `HEALTHCHECK` that polls this endpoint every 30 seconds, allowing container orchestrators to detect backend unavailability.
- The desktop backend manager (`desktop/src/backend.ts`) polls `/api/health` every 500 ms for up to 30 seconds after launch, ensuring the UI is not loaded against an unavailable backend.

### Idempotent Schedulers and Deduplication

Both the reminder and news push schedulers are designed to be safe under repeated execution:

- `persistence/alarm_store.py` uses `(deadline_id, lead_time)` as a composite primary key in `alarm_log`, recording each sent reminder. `alarm_service.py` checks `is_alarm_sent()` before sending and calls `mark_alarm_sent()` only on success.
- `persistence/news_push_store.py` uses `target_date` as the primary key in `news_push_log` with states `IN_PROGRESS`, `SUCCESS`, and `FAILED`. `try_claim_send()` atomically claims the send right for a given date; `record_send()` explicitly prevents a success state from being downgraded by a later failure.

Schedulers running every 60 seconds will not send duplicate notifications to users.

### Graceful Fallback for LLM-dependent Workflows

- `news_service.py`'s `create_ai_report()` falls back to a deterministic report when the LLM fails, returns unparseable output, or no articles are available.
- `news_push_service.py` uses a `_FallbackLLM` stub when no LLM provider is configured, triggering the same fallback path.
- The chat API supports session-level provider fallback: when `FallbackMode.AUTO` is set, the system tries the next available provider in priority order. A `PROVIDER_SWITCH` event is emitted to the frontend when this occurs.
- Users can configure fallback mode (manual or auto) via the Extension Service Settings panel.

### Persisted Partial State for Streaming Failures

- `conversation_tree_service.py` creates an assistant placeholder node before streaming begins, and calls `finalize_stream_turn()` to write the final content and status on completion.
- On stream exception or `HTTPException`, the placeholder is marked `FAILED` and any already-generated tokens, tool calls, and trace steps are persisted.
- The Vue chat store supports user-initiated stream interruption via `interruptSession()`, which saves partial output before stopping; on error, `persistPartialResponse()` is also attempted.

Users do not lose already-generated content on network interruption, LLM failure, or manual stop.

### Database Migrations and Backward Compatibility

The persistence layer includes forward migrations for schema evolution:

- `deadline_store.py` migrates non-nullable date fields to nullable and backfills `created_at`.
- `email_store.py` adds `folder`, `content_fetched`, and attachment download status columns, and can migrate a single-column `uid` primary key to a composite `(uid, folder)` key.
- `session_store.py` adds `selected_provider_id`, `fallback_mode`, `current_leaf_node_id`, and message status columns.
- `conversation_tree_store.py` adds `tool_calls` and `trace_steps` columns.

Existing user databases remain readable after upgrading the application.

### WAL Mode and Indexed Persistence

- `session_store.py` and `conversation_tree_store.py` enable `PRAGMA journal_mode=WAL` on file-backed SQLite databases, improving concurrent read/write performance and crash recovery.
- Frequently queried tables define explicit indexes: `idx_messages_session`, `idx_chat_nodes_version_group`, and an index on `email_uid` for attachments, among others.

---

## 4. User Experience

### Unified Three-Panel Workspace

`ChatView.vue` implements a **left sidebar / centre chat / right workspace** layout. The right workspace panel supports close and drag-to-resize (with enforced minimum/maximum bounds). The session sidebar supports a collapsed mode with tooltip labels for space efficiency. The workspace panel hosts domain-specific widgets, allowing Agent results to be presented as interactive UI components rather than plain text.

### Real-time Trace with Progressive Disclosure

`ChatTraceBlock.vue` places the ReAct loop, thinking steps, tool calls, and provider switches inside collapsible panels. Tool input/output details are only shown when `debug_mode` is enabled, keeping the default view clean. The reasoning engine (`engine/reasoning.py`) parses `<think>` blocks and separates internal reasoning from the final visible response; the Agent strips think blocks before persisting messages.

### Conversation Version Tree

The conversation tree service supports **retry**, **user edit**, and **assistant edit** operations, maintaining version groups and a selected-node pointer per branch. The chat message bubble exposes previous/next version navigation, edit, and retry controls. End-to-end version tree interactions are covered by `e2e/conversation-tree.spec.ts`.

### Internationalisation

The Vue frontend supports **English and Simplified Chinese**, with locale persisted in `localStorage` across sessions. Locale completeness is validated by `i18n/__tests__/locales.spec.ts`. The streaming chat API accepts an `X-Language` header, allowing the backend to select the appropriate skill prompt language.

### Clear Loading, Error, and Notification States

- The chat area shows typing dots, a streaming cursor, and failed/interrupted hints.
- Email detail loading uses a full-screen overlay with a cancel option; email actions (sync, star, download) provide toast feedback.
- `InboxWidget.vue` presents a modal prompt when credentials are missing, rather than silently failing.
- `DeadlineAlarmModal.vue` uses `role="dialog"`, `aria-modal="true"`, and `aria-label` for accessible alarm presentation.
- `composables/useNotificationPoller.ts` polls for pending notifications every 30 seconds, with an immediate check on startup.

### Rich Domain Widgets

The workspace panel includes purpose-built widgets for calendar, deadline panel, policy search, PDF viewer, email inbox, news digest, wrong-answer book, and quiz sections. These allow the Agent to surface structured, actionable results rather than returning raw text for every domain operation.

---

## 5. Maintainability and Engineering Quality

### Layered Architecture

The codebase follows a consistent **Controller → Service → Store** layering:

- `api/routes/*` handles HTTP concerns only.
- `services/*` contains all business logic, shared by both API routes and Agent tools.
- `persistence/*` handles all database access.
- `models/*` defines Pydantic/SQLModel DTOs and enums.

This means business rules are implemented once and reused across the API, the Agent tool system, and the CLI, without duplication.

### Typed Models and Enums

The backend uses Pydantic, SQLModel, and `StrEnum` throughout — `DeadlinePriority`, `DateType`, `EmailFlag`, `MailboxFolder`, `NewsPushStatus`, `MessageStatus`, and others. The frontend uses TypeScript with explicit type files (`chatTypes.ts`, `chatConstants.ts`). Both `ruff` (with strict configuration) and `vue-tsc --build` enforce type correctness in CI.

### Consistent Formatting and Language Policy

`scripts/check.sh` and the CI workflow enforce **Ruff** for Python and **Prettier** for Vue on every commit. A custom Semgrep rule (`semgrep-rules.yaml`) prohibits CJK characters in source code, scripts, and workflow files, ensuring that all Chinese-language content is managed exclusively through the i18n JSON files rather than scattered across the codebase.

### Monorepo Package Isolation

The project is split into four packages — `core` (FastAPI + Agent), `gui` (Vue 3), `cli` (Click), and `desktop` (Electron) — each with its own dependency file and test directory. The root `Taskfile.yml` provides unified task entry points (`task lint`, `task test`, `task ci`) while keeping package boundaries clean.

---

## 6. Deployment and Portability

### Docker Runtime

The multi-stage `Dockerfile` builds the GUI in a Node stage and runs the backend in a `uv:python3.12-bookworm-slim` stage. The production image does not retain frontend build tooling. A non-root `app` user owns `/app` and `/data`; `/data` is declared as a Docker volume for data persistence. The built-in `HEALTHCHECK` monitors the `/api/health` endpoint, enabling container orchestrators to detect unhealthy instances.

### Desktop Packaging

The Electron wrapper (`desktop/src/main.ts`) automatically starts the local backend and loads the GUI, requiring no manual setup from the end user. `desktop/src/paths.ts` copies a user-editable `.env` to the appropriate location and seeds default PDF data on first run. Backend stdout/stderr is written to `desktop-backend.log`, providing a diagnostic artefact for user-reported issues.