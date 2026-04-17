"""Multi-language prompts loader for the agent.

Loads evaluation and skill prompts from prompts.json, supporting multiple
languages. The default language is English.

Language is passed from the frontend via the X-Language request header
in the API call.
"""

import json
from pathlib import Path
from typing import Any

# Default language is English
DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en", "zh"}


def _get_prompts_dir() -> Path:
    """Get the directory containing prompts.json."""
    return Path(__file__).parent


def _load_prompts() -> dict[str, Any]:
    """Load all prompts from prompts.json."""
    prompts_path = _get_prompts_dir() / "prompts.json"
    with open(prompts_path, encoding="utf-8") as f:
        return json.load(f)


# Cache for loaded prompts
_prompts_cache: dict[str, Any] | None = None


def _get_prompts() -> dict[str, Any]:
    """Get cached prompts, loading if necessary."""
    global _prompts_cache
    if _prompts_cache is None:
        _prompts_cache = _load_prompts()
    return _prompts_cache


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
    prompts = _get_prompts()
    return prompts["evaluation"][question_type][lang]


def get_evaluation_header(question_type: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Get the evaluation header prompt for a question type.

    Args:
        question_type: Either "short_answer" or "fill_blank".
        language: Language code (e.g., "en" or "zh").

    Returns:
        The header prompt in the specified language.
    """
    lang = _validate_language(language)
    prompts = _get_prompts()
    return prompts["evaluation"]["headers"][lang][f"{question_type}_header"]


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
    prompts = _get_prompts()
    headers = prompts["evaluation"]["headers"][lang]
    no_answer = headers["no_answer"]

    template = headers["question_template"]
    return template.format(
        id=question_id,
        type=question_type,
        question=question_text,
        reference_answer=reference_answer,
        explanation=explanation or "N/A",
        user_answer=user_answer if user_answer.strip() else no_answer,
    )


def get_fallback_message(message_key: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Get a fallback message for evaluation.

    Args:
        message_key: One of auto_scored, choice_no_manual, no_answer,
            no_analysis, service_unavailable_auto, service_unavailable_manual.
        language: Language code (e.g., "en" or "zh").

    Returns:
        The fallback message in the specified language.
    """
    lang = _validate_language(language)
    prompts = _get_prompts()
    return prompts["evaluation"]["fallback_messages"][lang][message_key]


def get_course_assistant_prompt(language: str = DEFAULT_LANGUAGE) -> str:
    """Get the course assistant system prompt.

    Args:
        language: Language code (e.g., "en" or "zh").

    Returns:
        The system prompt in the specified language.
    """
    lang = _validate_language(language)
    prompts = _get_prompts()
    return prompts["course_assistant"]["system_prompt"][lang]


def get_quiz_title(language: str = DEFAULT_LANGUAGE) -> str:
    """Get the default quiz title.

    Args:
        language: Language code (e.g., "en" or "zh").

    Returns:
        The quiz title in the specified language.
    """
    lang = _validate_language(language)
    prompts = _get_prompts()
    return prompts["quiz"]["title"][lang]
