"""Helpers for separating `<think>` reasoning from visible assistant text."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

THINK_OPEN_TAG = "<think>"
THINK_CLOSE_TAG = "</think>"


class ReasoningSegmentKind(StrEnum):
    """Supported segment kinds produced by `<think>` parsing."""

    VISIBLE = "visible"
    THINKING = "thinking"


@dataclass(frozen=True)
class ReasoningSegment:
    """One ordered reasoning/text segment extracted from assistant output."""

    kind: ReasoningSegmentKind
    content: str


def has_think_protocol(text: str) -> bool:
    """Return True when the text contains the supported think protocol tags."""
    return THINK_OPEN_TAG in text or THINK_CLOSE_TAG in text


def _prefix_suffix_len(text: str, tag: str) -> int:
    """Return the longest suffix of text that could be the start of tag."""
    max_len = min(len(text), len(tag) - 1)
    for size in range(max_len, 0, -1):
        if tag.startswith(text[-size:]):
            return size
    return 0


class ReasoningStreamSplitter:
    """Incrementally split visible answer text from `<think>` reasoning blocks."""

    def __init__(self) -> None:
        self._buffer = ""
        self._inside_thinking = False
        self._saw_reasoning = False
        self._visible_started = False

    def feed_segments(self, text: str) -> list[ReasoningSegment]:
        """Consume the next streamed text chunk and preserve segment order."""
        if not text:
            return []
        self._buffer += text
        return self._consume(final=False)

    def feed(self, text: str) -> tuple[list[str], list[str]]:
        """Consume the next streamed text chunk.

        Returns visible-text fragments first and thinking fragments second.
        """
        return _group_segments(self.feed_segments(text))

    def flush_segments(self) -> list[ReasoningSegment]:
        """Flush any buffered content at stream end while preserving order."""
        segments = self._consume(final=True)
        if self._buffer:
            if self._inside_thinking:
                segments.append(
                    ReasoningSegment(ReasoningSegmentKind.THINKING, self._buffer)
                )
            else:
                self._append_visible(segments, self._buffer)
            self._buffer = ""
        return segments

    def flush(self) -> tuple[list[str], list[str]]:
        """Flush any buffered content at stream end."""
        return _group_segments(self.flush_segments())

    def _consume(self, *, final: bool) -> list[ReasoningSegment]:
        segments: list[ReasoningSegment] = []

        while self._buffer:
            if self._inside_thinking:
                close_index = self._buffer.find(THINK_CLOSE_TAG)
                if close_index >= 0:
                    fragment = self._buffer[:close_index]
                    if fragment:
                        segments.append(
                            ReasoningSegment(ReasoningSegmentKind.THINKING, fragment)
                        )
                    self._buffer = self._buffer[close_index + len(THINK_CLOSE_TAG) :]
                    self._inside_thinking = False
                    continue

                if final:
                    break

                keep_len = _prefix_suffix_len(self._buffer, THINK_CLOSE_TAG)
                emit_upto = len(self._buffer) - keep_len
                if emit_upto <= 0:
                    break
                fragment = self._buffer[:emit_upto]
                if fragment:
                    segments.append(
                        ReasoningSegment(ReasoningSegmentKind.THINKING, fragment)
                    )
                self._buffer = self._buffer[emit_upto:]
                break

            open_index = self._buffer.find(THINK_OPEN_TAG)
            if open_index >= 0:
                self._append_visible(segments, self._buffer[:open_index])
                self._buffer = self._buffer[open_index + len(THINK_OPEN_TAG) :]
                self._inside_thinking = True
                self._saw_reasoning = True
                continue

            if final:
                break

            keep_len = _prefix_suffix_len(self._buffer, THINK_OPEN_TAG)
            emit_upto = len(self._buffer) - keep_len
            if emit_upto <= 0:
                break
            self._append_visible(segments, self._buffer[:emit_upto])
            self._buffer = self._buffer[emit_upto:]
            break

        return segments

    def _append_visible(self, target: list[ReasoningSegment], fragment: str) -> None:
        if not fragment:
            return
        if self._saw_reasoning and not self._visible_started:
            fragment = fragment.lstrip()
        if not fragment:
            return
        self._visible_started = True
        target.append(ReasoningSegment(ReasoningSegmentKind.VISIBLE, fragment))


def _group_segments(
    segments: list[ReasoningSegment],
) -> tuple[list[str], list[str]]:
    """Split ordered segments into visible/thinking fragment lists."""
    visible: list[str] = []
    thinking: list[str] = []
    for segment in segments:
        if segment.kind == ReasoningSegmentKind.VISIBLE:
            visible.append(segment.content)
        else:
            thinking.append(segment.content)
    return visible, thinking


def split_reasoning_segments(text: str) -> list[ReasoningSegment]:
    """Split a full assistant text into ordered reasoning/text segments."""
    splitter = ReasoningStreamSplitter()
    segments = splitter.feed_segments(text)
    return [*segments, *splitter.flush_segments()]


def split_reasoning_blocks(text: str) -> tuple[list[str], str]:
    """Split a full assistant text into thinking segments and visible answer."""
    segments = split_reasoning_segments(text)
    visible_fragments, thinking_segments = _group_segments(segments)
    visible_text = "".join(visible_fragments)
    return thinking_segments, visible_text


def sanitize_visible_answer(text: str) -> str:
    """Remove supported `<think>` blocks from assistant-visible text."""
    _thinking, visible_text = split_reasoning_blocks(text)
    return visible_text
