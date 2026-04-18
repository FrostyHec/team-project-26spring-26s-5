"""Multi-language prompts loader for the agent.

Loads prompts from external .md files referenced by prompts.json index.
Supports multiple languages with fallback to English.

Language is passed from the frontend via the X-Language request header
in the API call.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

# Default language is English
DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en", "zh"}


def _get_prompts_dir() -> Path:
    """Get the directory containing the prompts index and .md files."""
    return Path(__file__).parent / "prompts"


def _load_index() -> dict[str, Any]:
    """Load the prompts index from prompts.json."""
    index_path = _get_prompts_dir() / "prompts.json"
    with open(index_path, encoding="utf-8") as f:
        return json.load(f)


# Cache for loaded index
_index_cache: dict[str, Any] | None = None


def _get_index() -> dict[str, Any]:
    """Get cached index, loading if necessary."""
    global _index_cache
    if _index_cache is None:
        _index_cache = _load_index()
    return _index_cache


@lru_cache(maxsize=32)
def _read_prompt_file(rel_path: str) -> str:
    """Read a prompt .md file by its relative path from the index."""
    prompts_dir = _get_prompts_dir()
    file_path = prompts_dir / rel_path
    return file_path.read_text(encoding="utf-8")


def _validate_language(lang: str) -> str:
    """Validate and return a supported language code."""
    if lang in SUPPORTED_LANGUAGES:
        return lang
    return DEFAULT_LANGUAGE


def get_evaluation_prompt(question_type: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Get the evaluation system prompt for a question type.

    Args:
        question_type: Either "short_answer" or "fill_blank".
        language: Language code (e.g., "en" or "zh").

    Returns:
        The system prompt in the specified language.
    """
    lang = _validate_language(language)
    index = _get_index()
    rel_path = index["evaluation"][question_type][lang]
    return _read_prompt_file(rel_path)


def get_course_assistant_prompt(language: str = DEFAULT_LANGUAGE) -> str:
    """Get the course assistant system prompt.

    Args:
        language: Language code (e.g., "en" or "zh").

    Returns:
        The system prompt in the specified language.
    """
    lang = _validate_language(language)
    index = _get_index()
    rel_path = index["course_assistant"]["system_prompt"][lang]
    return _read_prompt_file(rel_path)


# ---------------------------------------------------------------------------
# Question templates — read from .md files (contain placeholder formatting)
# ---------------------------------------------------------------------------


def build_evaluation_prompt(
    question_id: int,
    question_type: str,
    question_text: str,
    reference_answer: str,
    explanation: str,
    user_answer: str,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """Build the evaluation prompt for a single question.

    Args:
        question_id: The question ID.
        question_type: Question type (short_answer or fill_blank).
        question_text: The question text.
        reference_answer: The reference/correct answer.
        explanation: The explanation/key points.
        user_answer: The student's answer.
        language: Language code (e.g., "en" or "zh").

    Returns:
        Formatted evaluation prompt.
    """
    lang = _validate_language(language)
    index = _get_index()
    template = _read_prompt_file(index["evaluation"]["question_template"][lang])

    return template.format(
        id=question_id,
        type=question_type,
        question=question_text,
        reference_answer=reference_answer,
        explanation=explanation or "N/A",
        user_answer=user_answer if user_answer.strip() else "",
    )
