"""Blackboard integration — CAS login and deadline fetching.

Authenticates via SUSTech CAS, then fetches course deadlines from the
Blackboard Learn REST API.  All public functions carry full type
annotations (mypy strict mode).
"""

import asyncio
import re
import warnings
from logging import Logger
from typing import Any, TypedDict

import requests
from requests import Session
from urllib3.exceptions import InsecureRequestWarning

from agent_core.api.dependencies import get_profile_service
from agent_core.services.profile_service import ProfileService

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

HEADERS: dict[str, str] = {"user-agent": UA, "x-requested-with": "XMLHttpRequest"}
HEADERS_BB: dict[str, str] = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "Host": "bb.sustech.edu.cn",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": UA,
    "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
}

BB_BASE_URL = "https://bb.sustech.edu.cn"
BB_API_ENDPOINT = f"{BB_BASE_URL}/learn/api/public/v1"
BB_API_ENDPOINT_V2 = f"{BB_BASE_URL}/learn/api/public/v2"
BB_API_VERSION = "3900.0.0"
PAGE_SIZE = 100
_REQUEST_TIMEOUT = 10  # seconds
logger = Logger("blackboard_integration")


class CourseItem(TypedDict):
    id: str
    name: str


class DeadlineItem(TypedDict):
    title: str
    dueDate: str


BlackboardDeadlines = dict[str, list[DeadlineItem]]


def cas_login(sid: str, pwd: str) -> Session | None:
    """
    Reuse CAS login logic to obtain valid cookies for accessing Blackboard
    :param sid: Student ID
    :param pwd: CAS password
    :return: Logged-in Session object, returns None on failure
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        login_url = (
            "https://cas.sustech.edu.cn/cas/login?"
            "service=https%3A%2F%2Fbb.sustech.edu.cn/"
        )
        req = session.get(login_url, timeout=_REQUEST_TIMEOUT)
        if req.status_code != 200:
            logger.error("CAS login page returned status %d", req.status_code)
            return None
    except Exception as ex:
        print(f"Cannot access CAS, please check network connection ({ex})")
        logger.error("Cannot access CAS, please check network connection (%s)", ex)
        return None

    try:
        execution = re.findall(r'''name="execution" value="(.+?)"''', req.text)[0]
    except IndexError:
        logger.error("Failed to extract CAS execution parameter")
        return None

    data: dict[str, str] = {
        "username": sid,
        "password": pwd,
        "execution": execution,
        "_eventId": "submit",
        "geolocation": "",
    }

    try:
        req = session.post(
            login_url, data=data, allow_redirects=False, timeout=_REQUEST_TIMEOUT
        )
        if req.status_code == 500:
            logger.error("CAS service internal error")
            return None

        if "Location" not in req.headers:
            logger.error("Invalid username or password")
            return None

        resp = session.get(
            req.headers["Location"], allow_redirects=True, timeout=_REQUEST_TIMEOUT
        )
        session.get(
            f"{BB_BASE_URL}/learn/", headers=HEADERS_BB, timeout=_REQUEST_TIMEOUT
        )
        if "bb" in resp.url:
            logger.info("CAS login successful, Blackboard session established")
            return session
        else:
            logger.error("CAS login failed to redirect to Blackboard")
            return None
    except Exception as ex:
        logger.error("CAS login exception: %s", ex)
        return None


def get_bb_courses(session: requests.Session) -> list[dict[str, Any]]:
    """Retrieve the list of enrolled courses from the Blackboard calendar API.

    Args:
        session: An authenticated :class:`requests.Session`.

    Returns:
        List of course dictionaries (each has at least ``id`` and ``name``).
    """
    try:
        url = f"{BB_API_ENDPOINT}/calendars"
        resp = session.get(
            url,
            headers={**HEADERS_BB, "Referer": f"{BB_BASE_URL}/"},
            timeout=_REQUEST_TIMEOUT,
        )

        if resp.status_code != 200:
            logger.error(
                "Failed to get course list: %d - %s", resp.status_code, resp.text
            )
            return []

        data: dict[str, Any] = resp.json()
        if not data.get("results"):
            return []

        courses: list[dict[str, Any]] = [
            item for item in data["results"] if item["id"].startswith("_")
        ]
        logger.info("Retrieved %d courses", len(courses))
        return courses
    except Exception as ex:
        logger.error("Exception when getting course list: %s", ex)
        return []


def get_course_ddls(session: requests.Session, course_id: str) -> list[dict[str, str]]:
    """Fetch deadlines for a single course from the gradebook API.

    Args:
        session: An authenticated :class:`requests.Session`.
        course_id: Blackboard course ID.

    Returns:
        List of deadline dicts with ``title`` and ``dueDate`` keys.
    """
    try:
        url = f"{BB_API_ENDPOINT_V2}/courses/{course_id}/gradebook/columns"
        resp = session.get(
            url,
            headers={**HEADERS_BB, "Referer": f"{BB_BASE_URL}/"},
            timeout=_REQUEST_TIMEOUT,
        )

        if resp.status_code != 200:
            logger.error(
                "Failed to get course grades: %d - %s", resp.status_code, resp.text
            )
            return []

        data: dict[str, Any] = resp.json()
        if not data.get("results"):
            return []

        ddls: list[dict[str, str]] = []
        for item in data["results"]:
            if (
                isinstance(item, dict)
                and isinstance(item.get("name"), str)
                and isinstance(item.get("grading"), dict)
                and isinstance(item["grading"].get("due"), str)
            ):
                ddls.append({"title": item["name"], "dueDate": item["grading"]["due"]})
        return ddls
    except Exception as ex:
        logger.error("Exception when getting course grades: %s", ex)
        return []


def decorate_cookies(session: requests.Session) -> requests.Session:
    """Set additional cookies required by Blackboard.

    Args:
        session: Authenticated session to decorate.

    Returns:
        The same session (mutated in-place) with extra cookies set.
    """
    session.cookies.set("COOKIE_CONSENT_ACCEPTED", "true", domain="bb.sustech.edu.cn")
    session.cookies.set("CdnSignedValidation", "false", domain="bb.sustech.edu.cn")
    session.cookies.set(
        "BbClientCalenderTimeZone", "Asia/Shanghai", domain="bb.sustech.edu.cn"
    )
    session.cookies.set(
        "BbClientDownloadExecuting", "false", domain="bb.sustech.edu.cn"
    )
    return session


MOCK_BB_DATA: dict[str, list[dict[str, str]]] = {
    "Mock Course": [
        {"title": "Mock Assignment 1", "dueDate": "2026-07-02T08:00:00.000Z"}
    ],
}


def _fetch_all_ddls_sync(
    user_name: str, pass_word: str
) -> dict[str, list[dict[str, str]]]:
    """Blocking helper that performs CAS login and fetches deadlines.

    Runs synchronous ``requests`` calls.  Intended to be called inside
    :func:`asyncio.to_thread` so the event loop is not blocked.

    Raises:
        RuntimeError: If CAS login fails.
    """
    session = cas_login(user_name, pass_word)
    if not session:
        raise RuntimeError(
            f"CAS login failed ({user_name}, {'*' * len(pass_word)}). "
            "Please verify your CAS account/password in Settings."
        )

    session = decorate_cookies(session)
    courses = get_bb_courses(session)
    all_ddls: dict[str, list[dict[str, str]]] = {}
    for course in courses:
        all_ddls[course["name"]] = get_course_ddls(session, course["id"])

    return all_ddls


async def get_all_ddls(
    profile_service: ProfileService | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Fetch all course deadlines from Blackboard.

    CAS credentials are loaded from profile settings.  If *profile_service*
    is not supplied, the shared singleton is used.

    Args:
        profile_service: Optional explicit :class:`ProfileService` instance.

    Returns:
        Mapping of course name to a list of deadline dicts.

    Raises:
        RuntimeError: If CAS login fails or credentials are missing.
    """
    if profile_service is not None:
        logger.info("Using provided ProfileService instance")
    else:
        try:
            profile_service = get_profile_service()
        except RuntimeError as exc:
            raise RuntimeError(
                "ProfileService is not initialised. "
                "Ensure the application lifespan has started."
            ) from exc

    user_name, pass_word = await profile_service.get_decrypted_profile()

    if user_name == "mock_user_name" and pass_word == "mock_pass_word":
        logger.info("Using mock CAS credentials, returning mock data")
        return MOCK_BB_DATA

    # Run blocking HTTP I/O in a thread to avoid stalling the event loop
    return await asyncio.to_thread(_fetch_all_ddls_sync, user_name, pass_word)
