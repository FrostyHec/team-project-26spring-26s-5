"""File-backed persistence for agent memory topics."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from re import Pattern
from re import compile as re_compile

import yaml

from agent_core.models.agent_memory import (
    MemoryDocument,
    MemoryFrontmatter,
    MemoryUpdateMode,
)

MEMORY_DIR_NAME = "agent_memory"
BACKUP_DIR_NAME = ".backup"
MARKDOWN_SUFFIX = ".md"
FRONTMATTER_DELIMITER = "---"
FILENAME_PATTERN: Pattern[str] = re_compile(r"^[a-z0-9_-]+(?:\.md)?$")
INVALID_FILENAME_MESSAGE = (
    "Invalid filename. Use lowercase letters, numbers, underscores, or hyphens, "
    "with an optional .md suffix."
)


class AgentMemoryStore:
    """Persist agent memory topics as Markdown files under a dedicated root."""

    def __init__(self, data_root: str | Path) -> None:
        self._data_root = Path(data_root)
        self._memory_root = self._data_root / MEMORY_DIR_NAME
        self._backup_root = self._memory_root / BACKUP_DIR_NAME
        self._locks: dict[str, asyncio.Lock] = {}

    @property
    def memory_root(self) -> Path:
        """Return the topic storage root."""
        return self._memory_root

    @property
    def backup_root(self) -> Path:
        """Return the backup directory root."""
        return self._backup_root

    async def list_documents(self) -> list[MemoryDocument]:
        """Return all Markdown memory topics stored under the root."""
        await asyncio.to_thread(self._ensure_dirs)
        topic_files = await asyncio.to_thread(self._list_topic_files_sync)
        documents: list[MemoryDocument] = []
        for path in topic_files:
            raw_text = await asyncio.to_thread(path.read_text, encoding="utf-8")
            documents.append(self._parse_document(path.name, raw_text))
        return documents

    async def read_markdown(self, filename: str) -> str:
        """Return the raw Markdown text for one topic."""
        normalized_filename = self.normalize_filename(filename)
        path = self._topic_path(normalized_filename)
        if not path.exists():
            raise FileNotFoundError(f"Memory file not found: {normalized_filename}")
        return await asyncio.to_thread(path.read_text, encoding="utf-8")

    async def read_document(self, filename: str) -> MemoryDocument:
        """Return one parsed topic document."""
        normalized_filename = self.normalize_filename(filename)
        raw_text = await self.read_markdown(normalized_filename)
        return self._parse_document(normalized_filename, raw_text)

    async def create_document(
        self,
        filename: str,
        frontmatter: MemoryFrontmatter,
        content: str,
    ) -> MemoryDocument:
        """Create a new Markdown memory topic."""
        normalized_filename = self.normalize_filename(filename)
        path = self._topic_path(normalized_filename)
        lock = self._lock_for(normalized_filename)

        async with lock:
            await asyncio.to_thread(self._ensure_dirs)
            if path.exists():
                raise FileExistsError(
                    f"Memory file already exists: {normalized_filename}"
                )
            raw_text = self._render_document(frontmatter, content)
            await asyncio.to_thread(path.write_text, raw_text, encoding="utf-8")
        return self._parse_document(normalized_filename, raw_text)

    async def update_document(
        self,
        filename: str,
        mode: MemoryUpdateMode,
        content: str,
        timestamp: str,
        title: str | None = None,
        tags: list[str] | None = None,
        summary: str | None = None,
    ) -> MemoryDocument:
        """Append to or rewrite an existing Markdown memory topic."""
        normalized_filename = self.normalize_filename(filename)
        path = self._topic_path(normalized_filename)
        lock = self._lock_for(normalized_filename)

        async with lock:
            await asyncio.to_thread(self._ensure_dirs)
            if not path.exists():
                raise FileNotFoundError(f"Memory file not found: {normalized_filename}")

            original_text = await asyncio.to_thread(path.read_text, encoding="utf-8")
            existing_document = self._parse_document(normalized_filename, original_text)
            embedded_frontmatter: dict[str, object] = {}

            if mode == MemoryUpdateMode.APPEND:
                updated_body = self._append_content(existing_document.content, content)
            else:
                embedded_frontmatter, rewritten_body, has_frontmatter = (
                    self._split_frontmatter(content)
                )
                await asyncio.to_thread(
                    self._backup_document_sync,
                    path,
                    normalized_filename,
                    timestamp,
                )
                updated_body = (rewritten_body if has_frontmatter else content).strip()

            updated_frontmatter = self._merge_frontmatter(
                existing_document.frontmatter,
                embedded_frontmatter=embedded_frontmatter,
                title=title,
                tags=tags,
                summary=summary,
                timestamp=timestamp,
            )
            updated_text = self._render_document(updated_frontmatter, updated_body)
            await asyncio.to_thread(path.write_text, updated_text, encoding="utf-8")

        return self._parse_document(normalized_filename, updated_text)

    def normalize_filename(self, filename: str) -> str:
        """Validate and normalize an incoming topic filename."""
        candidate = filename.strip()
        if not candidate:
            raise ValueError(INVALID_FILENAME_MESSAGE)
        if not FILENAME_PATTERN.fullmatch(candidate):
            raise ValueError(INVALID_FILENAME_MESSAGE)
        if not candidate.endswith(MARKDOWN_SUFFIX):
            candidate = f"{candidate}{MARKDOWN_SUFFIX}"
        return candidate

    def _ensure_dirs(self) -> None:
        self._memory_root.mkdir(parents=True, exist_ok=True)
        self._backup_root.mkdir(parents=True, exist_ok=True)

    def _list_topic_files_sync(self) -> list[Path]:
        return sorted(
            path
            for path in self._memory_root.glob(f"*{MARKDOWN_SUFFIX}")
            if path.is_file()
        )

    def _lock_for(self, normalized_filename: str) -> asyncio.Lock:
        if normalized_filename not in self._locks:
            self._locks[normalized_filename] = asyncio.Lock()
        return self._locks[normalized_filename]

    def _topic_path(self, normalized_filename: str) -> Path:
        candidate = self._memory_root / normalized_filename
        resolved_root = self._memory_root.resolve()
        resolved_candidate = candidate.resolve()
        if resolved_root not in resolved_candidate.parents:
            raise ValueError(INVALID_FILENAME_MESSAGE)
        return resolved_candidate

    def _backup_document_sync(
        self,
        source_path: Path,
        normalized_filename: str,
        timestamp: str,
    ) -> None:
        backup_filename = f"{timestamp.replace(':', '-')}_{normalized_filename}"
        backup_path = self._backup_root / backup_filename
        shutil.copy2(source_path, backup_path)

    def _append_content(self, existing_content: str, new_content: str) -> str:
        existing = existing_content.rstrip()
        incoming = new_content.strip()
        if not existing:
            return incoming
        if not incoming:
            return existing
        return f"{existing}\n\n{incoming}"

    def _render_document(
        self,
        frontmatter: MemoryFrontmatter,
        content: str,
    ) -> str:
        frontmatter_text = yaml.safe_dump(
            frontmatter.model_dump(),
            allow_unicode=True,
            sort_keys=False,
        ).strip()
        body = content.strip()
        return (
            f"{FRONTMATTER_DELIMITER}\n"
            f"{frontmatter_text}\n"
            f"{FRONTMATTER_DELIMITER}\n\n"
            f"{body}\n"
        )

    def _parse_document(self, filename: str, raw_text: str) -> MemoryDocument:
        frontmatter, body, _ = self._split_frontmatter(raw_text)
        stem = Path(filename).stem
        document_frontmatter = MemoryFrontmatter(
            title=str(frontmatter.get("title") or stem),
            tags=self._normalize_tags(frontmatter.get("tags")),
            summary=str(frontmatter.get("summary") or ""),
            last_updated=str(frontmatter.get("last_updated") or ""),
        )
        return MemoryDocument(
            filename=filename,
            frontmatter=document_frontmatter,
            content=body.strip(),
        )

    def _split_frontmatter(self, raw_text: str) -> tuple[dict[str, object], str, bool]:
        lines = raw_text.splitlines()
        if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
            return {}, raw_text, False

        closing_index = -1
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == FRONTMATTER_DELIMITER:
                closing_index = index
                break

        if closing_index < 0:
            return {}, raw_text, False

        frontmatter_text = "\n".join(lines[1:closing_index])
        body = "\n".join(lines[closing_index + 1 :])
        try:
            loaded = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError:
            loaded = {}
        if not isinstance(loaded, dict):
            loaded = {}
        return loaded, body, True

    def _merge_frontmatter(
        self,
        existing_frontmatter: MemoryFrontmatter,
        *,
        embedded_frontmatter: dict[str, object],
        title: str | None,
        tags: list[str] | None,
        summary: str | None,
        timestamp: str,
    ) -> MemoryFrontmatter:
        updates: dict[str, object] = {"last_updated": timestamp}

        if "title" in embedded_frontmatter:
            updates["title"] = str(embedded_frontmatter.get("title") or "").strip()
        if "tags" in embedded_frontmatter:
            updates["tags"] = self._normalize_tags(embedded_frontmatter.get("tags"))
        if "summary" in embedded_frontmatter:
            updates["summary"] = str(embedded_frontmatter.get("summary") or "").strip()

        if title is not None:
            updates["title"] = title.strip()
        if tags is not None:
            updates["tags"] = [tag.strip() for tag in tags if tag.strip()]
        if summary is not None:
            updates["summary"] = summary.strip()

        return existing_frontmatter.model_copy(update=updates)

    def _normalize_tags(self, raw_tags: object) -> list[str]:
        if not isinstance(raw_tags, list):
            return []
        return [str(tag).strip() for tag in raw_tags if str(tag).strip()]
