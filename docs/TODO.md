# UI Redesign TODO — Align with Reference Flat/Clean Design

## Reference
- Design spec: `.nonpublic/developing_prompt/20260319_func_poc_dev/A009_UI绘制参考.md`
- Reference implementation: `.nonpublic/developing_prompt/20260319_func_poc_dev/app/src/App.vue`

---

## Completed Tasks

### ✅ T1: SessionSidebar — Compact Layout
- [x] Width: `w-64` (256px) instead of `w-[320px]`
- [x] Background: `bg-gray-50` with `border-r border-gray-200`
- [x] New Chat button: `bg-blue-600 rounded-lg py-2.5 text-sm` (compact)
- [x] Session items: `px-3 py-2.5 rounded-lg text-sm` with proper selected/hover states
- [x] Selected state: `bg-white shadow-sm border border-gray-200 text-blue-600`
- [x] User footer: `w-8 h-8` avatar (gray circle), compact settings icon

### ✅ T2: ChatHeader — Slim h-14
- [x] Height: `h-14` with `border-b border-gray-200`
- [x] Left: Session icon (MessageSquare) + session title (`text-base font-semibold`) + connection dot
- [x] Right: More button (...) + Panel toggle button (highlighted when open)
- [x] Backdrop blur: `bg-white/90 backdrop-blur-sm`

### ✅ T3: ChatMessageList — Clean Scroll Area
- [x] Remove `max-w-4xl mx-auto` centering constraint
- [x] Use `p-6 space-y-6 bg-gray-50/30` for subtle background
- [x] Compact empty state: 16x16 icon, `text-lg` heading, `text-sm` description

### ✅ T4: ChatMessageBubble — Compact & No Avatars
- [x] Remove 12px circular avatars beside messages
- [x] User: `bg-blue-600 text-white rounded-2xl rounded-tr-sm shadow-sm`
- [x] Assistant: `bg-white border border-gray-100 shadow-sm text-gray-800 rounded-2xl rounded-tl-sm`
- [x] Max width: `max-w-[80%]` for both
- [x] Sizing: `px-4 py-3 text-sm leading-relaxed`
- [x] Prose: `prose-sm` for assistant markdown

### ✅ T5: ChatInputBox — Flat Input Bar
- [x] Remove absolute positioning with gradient overlay
- [x] Use static `p-4 bg-white border-t border-gray-100 flex-shrink-0`
- [x] Input composite: `border border-gray-300 rounded-xl shadow-sm`
- [x] Paperclip (p-3) + textarea (text-sm) + Send button (p-2 m-1.5 rounded-lg)
- [x] Skill pills below: `text-[10px] rounded-full` with color variants
- [x] Remove "AI can make mistakes" disclaimer

### ✅ T6: ChatToolBadges — Capsule Style
- [x] Capsule: `rounded-full bg-gray-50 border border-gray-100`
- [x] Icons: `w-3.5 h-3.5` (smaller)
- [x] Font: `text-xs font-medium text-gray-500`

### ✅ T7: WorkspacePanel — Clean Header
- [x] Default width: 320px (was 400px)
- [x] Header: `px-4 py-3 border-b border-gray-200` (no shadow)
- [x] Title: `text-sm font-semibold text-gray-800`

### ✅ T8: ChatView — 3-Column Layout
- [x] Background: `bg-white` (not gray)
- [x] Center panel: `flex-1 min-w-[350px]` (no shadow-2xl)
- [x] Right panel: subtle left shadow `box-shadow: -4px 0 15px -3px rgba(0,0,0,0.05)`
- [x] Slide transition: smooth ease with translateX

### ✅ T9: Global CSS
- [x] Font: Inter as primary font family
- [x] Thin scrollbar: 4px, subtle gray thumb
- [x] Textarea auto-resize support

---

## Verification Checklist
- [x] 3-column layout visible (sidebar + chat + workspace)
- [x] Sidebar is narrow (256px), compact items
- [x] Header is slim (56px), shows session title
- [x] Messages use compact bubbles without avatars
- [x] Input is flat, at bottom, not overlapping messages
- [x] Skill pills are small capsules below input
- [x] Workspace panel is 320px default with clean header
- [x] All hover states and transitions work
- [x] No TypeScript/compilation errors
