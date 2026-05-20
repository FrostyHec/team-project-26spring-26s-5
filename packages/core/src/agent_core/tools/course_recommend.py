"""Course recommendation tools backed by a packaged course catalog.

The catalog is stored as package data under ``agent_core.resources`` so the
tools no longer depend on temporary local files. Recommendation can optionally
fold in Agent Memory topics and makes that personalization visible in the JSON
response.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from typing import Any

from agent_core.persistence.agent_memory_provider import get_agent_memory_service
from agent_core.tools.registry import ToolRegistry, ToolSensitivity

_DEFAULT_LIMIT = 5
_CATALOG_RESOURCE = "course_catalog.json"
_MAX_MEMORY_TOPICS = 3
_MAX_MEMORY_CHARS = 4000

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}

_INTEREST_ALIASES: dict[str, tuple[str, ...]] = {
    "ai": ("ai", "artificial intelligence", "\u4eba\u5de5\u667a\u80fd"),
    "machine learning": ("machine learning", "ml", "\u673a\u5668\u5b66\u4e60"),
    "data": ("data", "data science", "\u6570\u636e"),
    "algorithm": ("algorithm", "algorithms", "\u7b97\u6cd5"),
    "programming": ("programming", "python", "java", "\u7a0b\u5e8f"),
    "robotics": ("robot", "robotics", "\u673a\u5668\u4eba"),
    "vision": ("vision", "computer vision", "\u89c6\u89c9"),
    "language": ("nlp", "natural language", "\u81ea\u7136\u8bed\u8a00"),
}

_DEPARTMENT_ALIASES: dict[str, tuple[str, ...]] = {
    "computer science": (
        "computer science",
        "cs",
        "cse",
        "\u8ba1\u7b97\u673a",
    ),
    "data science": ("data science", "\u7edf\u8ba1", "\u6570\u636e"),
    "engineering": ("engineering", "\u5de5\u5b66", "\u5de5\u7a0b"),
}

_LANGUAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "english": ("english", "\u82f1\u6587"),
    "chinese": ("chinese", "\u4e2d\u6587"),
    "bilingual": ("bilingual", "\u53cc\u8bed"),
}

_DAY_ALIASES: dict[str, str] = {
    "monday": "\u661f\u671f\u4e00",
    "tuesday": "\u661f\u671f\u4e8c",
    "wednesday": "\u661f\u671f\u4e09",
    "thursday": "\u661f\u671f\u56db",
    "friday": "\u661f\u671f\u4e94",
    "saturday": "\u661f\u671f\u516d",
    "sunday": "\u661f\u671f\u65e5",
}

Course = dict[str, Any]


@lru_cache(maxsize=1)
def _load_catalog() -> list[Course]:
    """Load the packaged catalog once per process."""
    resource = files("agent_core.resources").joinpath(_CATALOG_RESOURCE)
    raw = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _normalize(value: object) -> str:
    return str(value or "").strip().lower()


def _safe_limit(limit: int) -> int:
    return limit if limit > 0 else _DEFAULT_LIMIT


def _split_terms(value: str) -> list[str]:
    """Return searchable terms from free text, preserving non-ASCII words."""
    text = _normalize(value)
    terms = re.findall(r"[^\W_]+(?:[-'][^\W_]+)?", text, flags=re.UNICODE)
    return [term for term in terms if len(term) > 1 and term not in _STOPWORDS]


def _expand_terms(value: str) -> list[str]:
    terms = set(_split_terms(value))
    lowered = _normalize(value)
    for aliases in _INTEREST_ALIASES.values():
        if any(alias in lowered for alias in aliases):
            terms.update(aliases)
    return sorted(terms)


def _course_code_from_class_id(class_id: str) -> str:
    parts = class_id.split("-")
    return parts[-2] if len(parts) >= 2 else class_id


def _base_course_name(class_name: str) -> str:
    return class_name.split("-", maxsplit=1)[0].strip() or class_name


def _course_search_text(course: Course) -> str:
    return " ".join(
        str(course.get(key, ""))
        for key in (
            "id",
            "system_id",
            "class_id",
            "course_code",
            "class_name",
            "department",
            "instructor",
            "schedule",
            "course_type",
            "course_language",
        )
    ).lower()


def _course_description(course: Course) -> str:
    parts = [
        str(course.get("department") or ""),
        str(course.get("course_type") or ""),
        str(course.get("course_language") or ""),
        str(course.get("schedule") or ""),
    ]
    return " | ".join(part for part in parts if part)


def _public_course_fields(course: Course) -> Course:
    class_name = str(course.get("class_name") or "")
    total_hours = course.get("total_hours")
    workload = f"{total_hours:g} hours" if isinstance(total_hours, int | float) else ""
    return {
        "id": course.get("id", ""),
        "system_id": course.get("system_id", ""),
        "class_id": course.get("class_id", ""),
        "code": course.get("course_code")
        or _course_code_from_class_id(str(course.get("class_id") or "")),
        "name": _base_course_name(class_name),
        "class_name": class_name,
        "department": course.get("department", ""),
        "credits": course.get("credits"),
        "total_hours": course.get("total_hours"),
        "workload": workload,
        "instructor": course.get("instructor", ""),
        "schedule": course.get("schedule", ""),
        "course_type": course.get("course_type", ""),
        "course_language": course.get("course_language", ""),
        "ug_quota": course.get("ug_quota"),
        "pg_quota": course.get("pg_quota"),
        "description": _course_description(course),
    }


def _matches_filter(
    course: Course,
    *,
    keyword: str = "",
    department: str = "",
    instructor: str = "",
    course_type: str = "",
    course_language: str = "",
    min_credits: float | None = None,
    max_credits: float | None = None,
) -> bool:
    search_text = _course_search_text(course)
    if keyword and not any(term in search_text for term in _expand_terms(keyword)):
        return False
    if department and not _matches_department(course, department):
        return False
    if instructor and _normalize(instructor) not in _normalize(
        course.get("instructor")
    ):
        return False
    if course_type and _normalize(course_type) not in _normalize(
        course.get("course_type")
    ):
        return False
    if course_language and not _matches_language(course, course_language):
        return False
    credits = course.get("credits")
    if isinstance(credits, int | float):
        if min_credits is not None and credits < min_credits:
            return False
        if max_credits is not None and credits > max_credits:
            return False
    return True


def _matches_department(course: Course, department: str) -> bool:
    course_department = _normalize(course.get("department"))
    requested = _normalize(department)
    if requested in course_department:
        return True
    aliases = _DEPARTMENT_ALIASES.get(requested, ())
    return any(alias in course_department for alias in aliases)


def _matches_language(course: Course, course_language: str) -> bool:
    catalog_language = _normalize(course.get("course_language"))
    requested = _normalize(course_language)
    if requested in catalog_language:
        return True
    aliases = _LANGUAGE_ALIASES.get(requested, ())
    return any(alias in catalog_language for alias in aliases)


def _find_course(identifier: str) -> Course | None:
    target = _normalize(identifier)
    if not target:
        return None

    catalog = _load_catalog()
    for course in catalog:
        exact_values = [
            str(course.get("id") or ""),
            str(course.get("class_id") or ""),
            str(course.get("system_id") or ""),
            str(course.get("course_code") or ""),
        ]
        if any(_normalize(value) == target for value in exact_values):
            return course

    for course in catalog:
        if target in _course_search_text(course):
            return course
    return None


def _parse_requested_ids(course_ids_json: str) -> list[str]:
    try:
        raw_ids = json.loads(course_ids_json)
    except (json.JSONDecodeError, TypeError):
        raw_ids = [course_ids_json]
    if not isinstance(raw_ids, list):
        raw_ids = [raw_ids]
    return [str(item).strip() for item in raw_ids if str(item).strip()]


def _completed_codes(completed_courses: str, memory_text: str = "") -> set[str]:
    text = f"{completed_courses} {memory_text}"
    return {item.upper() for item in re.findall(r"\b[A-Z]{2,5}\d{2,4}\b", text)}


def _infer_department(value: str) -> str:
    lowered = _normalize(value)
    for department, aliases in _DEPARTMENT_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return department
    return ""


def _infer_language(value: str) -> str:
    lowered = _normalize(value)
    for language, aliases in _LANGUAGE_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return language
    return ""


def _schedule_penalties(value: str) -> list[str]:
    lowered = _normalize(value)
    penalties: list[str] = []
    for label, day_text in _DAY_ALIASES.items():
        if label in lowered or day_text in lowered:
            penalties.append(day_text)
    return penalties


def _memory_topic_is_relevant(topic: Any) -> bool:
    text = " ".join(
        [
            getattr(topic, "filename", ""),
            getattr(topic, "title", ""),
            getattr(topic, "summary", ""),
            " ".join(getattr(topic, "tags", []) or []),
        ]
    ).lower()
    return any(
        marker in text
        for marker in (
            "course",
            "courses",
            "recommend",
            "preference",
            "profile",
            "study",
            "academic",
        )
    )


async def _collect_memory_context(
    include_memory: bool,
) -> tuple[str, list[dict[str, str]]]:
    if not include_memory:
        return "", []
    try:
        service = await get_agent_memory_service()
        topics = await service.list_topics()
        selected = [topic for topic in topics if _memory_topic_is_relevant(topic)]
        chunks: list[str] = []
        topic_refs: list[dict[str, str]] = []
        for topic in selected[:_MAX_MEMORY_TOPICS]:
            text = await service.read_memory_file(topic.filename)
            chunks.append(text[:_MAX_MEMORY_CHARS])
            topic_refs.append(
                {
                    "filename": topic.filename,
                    "title": topic.title,
                    "summary": topic.summary,
                }
            )
        return "\n\n".join(chunks), topic_refs
    except Exception:
        return "", []


def _score_course(
    course: Course,
    *,
    interests: str,
    major: str,
    completed_courses: str,
    preferred_language: str,
    avoid_schedule: str,
    memory_text: str,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    search_text = _course_search_text(course)

    for term in _expand_terms(f"{interests} {memory_text}"):
        if term in search_text:
            score += 3
            reasons.append(f"matches interest '{term}'")

    inferred_major = _normalize(major) or _infer_department(memory_text)
    if inferred_major and _matches_department(course, inferred_major):
        score += 3
        reasons.append(f"fits department '{course.get('department', '')}'")

    language = _normalize(preferred_language) or _infer_language(memory_text)
    if language:
        aliases = _LANGUAGE_ALIASES.get(language, (language,))
        course_language = _normalize(course.get("course_language"))
        if any(alias in course_language for alias in aliases):
            score += 2
            reasons.append(
                f"matches preferred language '{course.get('course_language')}'"
            )

    completed = _completed_codes(completed_courses, memory_text)
    course_code = str(course.get("course_code") or "").upper()
    if course_code and course_code in completed:
        return -100, ["already completed"]

    credits = course.get("credits")
    if isinstance(credits, int | float) and 1 <= credits <= 4:
        score += 1
        reasons.append("reasonable credit load")

    quota = course.get("ug_quota")
    if isinstance(quota, int | float) and quota > 0:
        score += 1
        reasons.append("has undergraduate quota")

    schedule_penalty_text = f"{avoid_schedule} {memory_text}"
    for day_text in _schedule_penalties(schedule_penalty_text):
        if day_text and day_text in str(course.get("schedule") or ""):
            score -= 2
            reasons.append("conflicts with remembered schedule preference")

    return score, reasons


def get_course_catalog(
    keyword: str = "",
    department: str = "",
    level: str = "",
    instructor: str = "",
    course_type: str = "",
    course_language: str = "",
    min_credits: float | None = None,
    max_credits: float | None = None,
    limit: int = _DEFAULT_LIMIT,
) -> str:
    """Search the local course catalog."""
    selected_type = course_type or level
    courses = [
        _public_course_fields(course)
        for course in _load_catalog()
        if _matches_filter(
            course,
            keyword=keyword,
            department=department,
            instructor=instructor,
            course_type=selected_type,
            course_language=course_language,
            min_credits=min_credits,
            max_credits=max_credits,
        )
    ]
    return json.dumps(courses[: _safe_limit(limit)], ensure_ascii=False)


async def recommend_courses(
    interests: str = "",
    major: str = "",
    year: str = "",
    completed_courses: str = "",
    preferred_language: str = "",
    avoid_schedule: str = "",
    memory_context: str = "",
    include_memory: bool = True,
    limit: int = _DEFAULT_LIMIT,
) -> str:
    """Recommend courses from the local catalog using profile and memory hints."""
    stored_memory, memory_topics = await _collect_memory_context(include_memory)
    combined_memory = "\n\n".join(
        part for part in [memory_context, stored_memory] if part
    )

    scored_courses: list[Course] = []
    for course in _load_catalog():
        score, reasons = _score_course(
            course,
            interests=interests,
            major=major,
            completed_courses=completed_courses,
            preferred_language=preferred_language,
            avoid_schedule=avoid_schedule,
            memory_text=combined_memory,
        )
        if score > 0:
            item = _public_course_fields(course)
            item["score"] = score
            item["rating"] = min(5.0, max(1.0, round(score / 2, 1)))
            item["reasons"] = reasons
            scored_courses.append(item)

    scored_courses.sort(
        key=lambda item: (
            item.get("score", 0),
            item.get("credits") or 0,
            str(item.get("code", "")),
        ),
        reverse=True,
    )
    recommendations = scored_courses[: _safe_limit(limit)]
    return json.dumps(
        {
            "profile": {
                "interests": interests,
                "major": major or _infer_department(combined_memory),
                "year": year,
                "completed_courses": sorted(
                    _completed_codes(completed_courses, combined_memory)
                ),
                "preferred_language": preferred_language
                or _infer_language(combined_memory),
                "avoid_schedule": avoid_schedule,
            },
            "memory_used": {
                "enabled": include_memory,
                "topics": memory_topics,
                "explicit_context_provided": bool(memory_context.strip()),
            },
            "count": len(recommendations),
            "recommendations": recommendations,
        },
        ensure_ascii=False,
    )


def get_course_detail(course_id: str) -> str:
    """Fetch detailed information for a single course by id, code, or keyword."""
    course = _find_course(course_id)
    if course is None:
        return json.dumps(
            {"error": f"Course not found: {course_id}"},
            ensure_ascii=False,
        )
    return json.dumps(_public_course_fields(course), ensure_ascii=False)


def compare_courses(course_ids_json: str) -> str:
    """Compare multiple courses side by side."""
    found: list[Course] = []
    missing: list[str] = []
    for course_id in _parse_requested_ids(course_ids_json):
        course = _find_course(course_id)
        if course is None:
            missing.append(course_id)
            continue
        public = _public_course_fields(course)
        found.append(
            {
                "id": public["id"],
                "code": public["code"],
                "name": public["name"],
                "class_name": public["class_name"],
                "department": public["department"],
                "credits": public["credits"],
                "total_hours": public["total_hours"],
                "workload": public["workload"],
                "instructor": public["instructor"],
                "schedule": public["schedule"],
                "course_type": public["course_type"],
                "course_language": public["course_language"],
                "ug_quota": public["ug_quota"],
                "pg_quota": public["pg_quota"],
            }
        )

    return json.dumps({"courses": found, "missing": missing}, ensure_ascii=False)


_TOOL_DESCRIPTIONS: list[tuple[Any, str, ToolSensitivity]] = [
    (
        get_course_catalog,
        "Search the packaged course catalog. Optional filters: keyword, "
        "department, instructor, course_type, course_language, min_credits, "
        "max_credits, and limit. Returns class id, course code, name, credits, "
        "instructor, schedule, quota, type, and language fields.",
        ToolSensitivity.SAFE,
    ),
    (
        recommend_courses,
        "Recommend courses from the packaged catalog. Pass interests, major, "
        "year, completed_courses, preferred_language, avoid_schedule, "
        "memory_context, include_memory, and limit. For personalized "
        "recommendations, first inspect Agent Memory with list_memory_topics "
        "and read_memory_file, then pass relevant notes as memory_context. "
        "The response exposes memory_used and reasons for each recommendation.",
        ToolSensitivity.SAFE,
    ),
    (
        get_course_detail,
        "Fetch detailed information for one course by class_id, system_id, "
        "course code, or keyword.",
        ToolSensitivity.SAFE,
    ),
    (
        compare_courses,
        "Compare multiple courses side by side. Pass course_ids_json as a JSON "
        "array of class ids, system ids, course codes, or course-name keywords. "
        "Returns credits, hours, instructor, schedule, type, language, quota, "
        "and missing ids.",
        ToolSensitivity.SAFE,
    ),
]


def register_course_recommend_tools(registry: ToolRegistry) -> None:
    """Register all course recommendation tools with the given registry."""
    for func, description, sensitivity in _TOOL_DESCRIPTIONS:
        registry.add_tool(func=func, description=description, sensitivity=sensitivity)
