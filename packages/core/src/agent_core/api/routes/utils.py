"""Common route utilities."""

from fastapi import Header

from agent_core.prompts_loader import DEFAULT_LANGUAGE


def get_language(x_language: str = Header(default=DEFAULT_LANGUAGE)) -> str:
    """Extract language from X-Language header or default to English.

    FastAPI automatically converts x_language to X-Language (underscore → hyphen).
    """
    return x_language
