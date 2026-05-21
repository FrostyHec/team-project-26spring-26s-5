"""Blackboard integration — CAS login and deadline fetching.

Authenticates via SUSTech CAS, then fetches course deadlines from the
Blackboard Learn REST API.  All public functions carry full type
annotations (mypy strict mode).
"""

import asyncio
import html
import os
import re
import warnings
from logging import Logger
from typing import Any, TypedDict

import requests
from requests import Session
from urllib3.exceptions import InsecureRequestWarning

from agent_core.api.dependencies import get_profile_service
from agent_core.services.profile_service import ProfileService
from agent_core.tools.registry import ToolRegistry

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


def get_course_contents(
    session: requests.Session, course_id: str
) -> list[dict[str, Any]]:
    """Retrieve the list of courses from the Blackboard calendar API.

    Args:
        session: An authenticated :class:`requests.Session`.
        course_id: Blackboard course ID, e.g., "_8012_1".

    Returns:
        List of course dictionaries (each has at least ``id`` and ``name``).
    """
    try:
        # Try v1 first, fallback to v2 if needed
        url = f"{BB_API_ENDPOINT}/courses/{course_id}/contents"
        resp = session.get(
            url,
            headers={**HEADERS_BB, "Referer": f"{BB_BASE_URL}/"},
            timeout=_REQUEST_TIMEOUT,
        )

        if resp.status_code != 200:
            url = f"{BB_API_ENDPOINT_V2}/courses/{course_id}/contents"
            resp = session.get(
                url,
                headers={**HEADERS_BB, "Referer": f"{BB_BASE_URL}/"},
                timeout=_REQUEST_TIMEOUT,
            )

            if resp.status_code != 200:
                logger.error(
                    "Failed to get course contents: %d - %s",
                    resp.status_code,
                    resp.text,
                )
                return []

        data: dict[str, Any] = resp.json()
        if not data.get("results"):
            return []

        contents: list[dict[str, Any]] = []
        for raw_content in data["results"]:
            if isinstance(raw_content, dict):
                contents.append(
                    {
                        "course_id": course_id,  # e.g., "_8012_1"
                        "content_id": raw_content["id"],  # e.g., "_588338_1"
                        "title": raw_content["title"],  # e.g., "Lectures"
                    }
                )

        logger.info("Retrieved %d contents", len(contents))
        return contents
    except Exception as ex:
        logger.error("Exception when getting course contents: %s", ex)
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


MOCK_BB_DDL_DATA: dict[str, list[dict[str, str]]] = {
    "Mock Course": [
        {"title": "Mock Assignment 1", "dueDate": "2026-07-02T08:00:00.000Z"}
    ],
}

MOCK_BB_COURSE_DATA = [
    {
        "id": "_8012_1",
        "courseId": "CS304-30018694-2026SP",
        "name": "Software Engineering Spring 2026",
        "organization": False,
        "ultraStatus": "Classic",
        "readOnly": False,
        "termId": "_57_1",
        "availability": {"available": "Yes", "duration": {"type": "Term"}},
        "enrollment": {"type": "InstructorLed"},
        "locale": {"id": "en_US", "force": True},
        "externalAccessUrl": "https://bb.sustech.edu.cn/webapps/blackboard/execute/courseMain?course_id=_8012_1&sc=",
        "guestAccessUrl": "https://bb.sustech.edu.cn/webapps/blackboard/execute/courseMain?course_id=_8012_1&sc=",
    }
]

MOCK_BB_CONTENT_DATA = [
    {
        "course_id": "_8012_1",
        "content_id": "_588340_1",
        "title": "Lectures",
    }
]


def _fetch_all_courses_sync(user_name: str, pass_word: str) -> list[dict[str, Any]]:
    """Blocking helper that performs CAS login and fetches courses.

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
    return courses


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


def _fetch_course_contents_sync(
    user_name: str, pass_word: str, course_id: str
) -> dict[str, list[dict[str, str]]]:
    """Blocking helper that performs CAS login and fetches contents.

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
    contents = get_course_contents(session, course_id)
    return contents


async def get_all_courses(
    profile_service: ProfileService | None = None,
) -> list[dict[str, Any]]:
    """Fetch all enrolled courses from Blackboard.

    CAS credentials are loaded from profile settings.  If *profile_service*
    is not supplied, the shared singleton is used.

    Args:
        profile_service: Optional explicit :class:`ProfileService` instance.

    Returns:
        List of course dictionaries (each has at least ``id`` and ``name``).

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
        logger.info("Using mock CAS credentials, returning empty list")
        return MOCK_BB_COURSE_DATA

    return await asyncio.to_thread(_fetch_all_courses_sync, user_name, pass_word)


async def get_all_contents_of_course(
    course_id: str,
    profile_service: ProfileService | None = None,
) -> list[dict[str, Any]]:
    """Fetch all contents of a specific course from Blackboard.

    CAS credentials are loaded from profile settings.  If *profile_service*
    is not supplied, the shared singleton is used.

    Args:
        course_id: Blackboard course ID, e.g., "_8012_1".
        profile_service: Optional explicit :class:`ProfileService` instance.

    Returns:
        List of course dictionaries (each has at least ``id`` and ``name``).

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
        logger.info("Using mock CAS credentials, returning empty list")
        return MOCK_BB_CONTENT_DATA

    return await asyncio.to_thread(
        _fetch_course_contents_sync, user_name, pass_word, course_id
    )


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
        return MOCK_BB_DDL_DATA

    # Run blocking HTTP I/O in a thread to avoid stalling the event loop
    return await asyncio.to_thread(_fetch_all_ddls_sync, user_name, pass_word)


def check_file_type(file_path: str) -> str:
    """Check the file type of a file based on its header.

    Args:
        file_path: Path to the file to check.

    Returns:
        The file type as a string, or an empty string if unknown.
    """
    with open(file_path, "rb") as f:
        header = f.read(1024)

    if header.startswith(b"%PDF-"):
        return "pdf"

    if header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        if b"WordDocument" in header:
            return "doc"
        elif b"PowerPoint Document" in header:
            return "ppt"
        else:
            return ""

    if header.startswith(b"PK\x03\x04"):
        if b"word/" in header:
            return "docx"
        elif b"ppt/" in header:
            return "pptx"
        else:
            return ""

    return ""


def download_bb_resources(
    url: str,
    local_dir: str,
    session: requests.Session,
) -> list[str]:
    """Download resources from a Blackboard page that start with bbcswebdav/pid- URL.

    Args:
        url: The Blackboard page URL to parse for resources. If URL itself starts
            with /bbcswebdav/pid-, directly download that file.
        local_dir: Local directory to save downloaded files.
        session: An authenticated :class:`requests.Session`.

    Returns:
        List of downloaded file paths.
    """
    try:
        if not url:
            logger.error("Blackboard resource download skipped: URL is empty")
            return []

        if url.startswith("/bbcswebdav/pid-") or url.startswith(
            f"{BB_BASE_URL}/bbcswebdav/pid-"
        ):
            if url.startswith("/bbcswebdav/pid-"):
                full_url = f"{BB_BASE_URL}{url}"
            else:
                full_url = url
                url = url.split(BB_BASE_URL)[1]
            filename = os.path.basename(url)
            local_path = os.path.join(local_dir, filename)
            os.makedirs(local_dir, exist_ok=True)

            resp = session.get(
                full_url,
                headers={**HEADERS_BB, "Referer": f"{BB_BASE_URL}/"},
                timeout=_REQUEST_TIMEOUT,
                stream=True,
            )

            if resp.status_code == 200:
                with open(local_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                file_type = check_file_type(local_path)
                if file_type and not local_path.endswith(f".{file_type}"):
                    file_path = os.path.join(
                        local_dir, f"{filename.split('.')[0]}.{file_type}"
                    )
                    os.rename(local_path, file_path)
                    local_path = file_path
                logger.info(f"Downloaded: {local_path}")
                return [local_path]
            else:
                logger.error("Failed to download %s: %d", full_url, resp.status_code)
                return []

        resp = session.get(
            url,
            headers={**HEADERS_BB, "Referer": f"{BB_BASE_URL}/"},
            timeout=_REQUEST_TIMEOUT,
        )

        if resp.status_code != 200:
            logger.error(
                "Failed to fetch page: %d - %s",
                resp.status_code,
                resp.text[:500],
            )
            return []

        logger.info(
            "Page fetched successfully, status: %d, content length: %d",
            resp.status_code,
            len(resp.text),
        )

        resource_urls = re.findall(r'/bbcswebdav/pid-[^\s"\']+', resp.text)

        if not resource_urls:
            logger.warning(
                "No bbcswebdav resources found on page. "
                "Page content (first 2000 chars): %s",
                resp.text[:2000],
            )
            # Additional debug: look for any resource-related patterns
            bb_patterns = re.findall(r'bbcswebdav[^\s"\'<>]*', resp.text)
            if bb_patterns:
                logger.info(
                    "Found bbcswebdav patterns (different format): %s",
                    bb_patterns[:10],
                )
            # Also look for iframe src which might contain the actual content
            iframe_patterns = re.findall(
                r'<iframe[^>]+src=["\']([^"\']+)["\']', resp.text
            )
            if iframe_patterns:
                logger.info("Found iframe sources: %s", iframe_patterns[:5])
            return []

        logger.info("Found %d bbcswebdav resource URLs", len(resource_urls))

        resource_url_to_filename: dict[str, str] = {}
        for line in resp.text.splitlines():
            if "/bbcswebdav/pid-" in line:
                full_url_start = line.find('href="') + 6
                full_url_end = line.find('"', full_url_start)
                full_url = line[full_url_start:full_url_end]
                if line.endswith("</span></a>"):
                    filename = line.split(">")[-3].split("<")[0].strip()
                elif line.endswith("</a>"):
                    filename = line.split(">")[-2].split("<")[0].strip()
                resource_url_to_filename[full_url] = html.unescape(filename).strip()

        os.makedirs(local_dir, exist_ok=True)
        downloaded_files: list[str] = []
        resource_full_urls = [
            f"{BB_BASE_URL}{resource_url}" for resource_url in resource_urls
        ]

        for resouce_url, resource_full_url in zip(
            resource_urls, resource_full_urls, strict=True
        ):
            try:
                filename = resource_url_to_filename.get(
                    resouce_url,
                    resource_url_to_filename.get(
                        resource_full_url, os.path.basename(resource_full_url)
                    ),
                )
                local_path = os.path.join(local_dir, filename)

                resp = session.get(
                    resource_full_url,
                    headers={**HEADERS_BB, "Referer": url},
                    timeout=_REQUEST_TIMEOUT,
                    stream=True,
                )

                if resp.status_code == 200:
                    with open(local_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    file_type = check_file_type(local_path)
                    if file_type and not local_path.endswith(f".{file_type}"):
                        file_path = os.path.join(
                            local_dir, f"{filename.split('.')[0]}.{file_type}"
                        )
                        os.rename(local_path, file_path)
                        downloaded_files.append(file_path)
                        logger.info(f"Downloaded: {file_path}")
                    else:
                        downloaded_files.append(local_path)
                        logger.info(f"Downloaded: {local_path}")
                else:
                    logger.warning(
                        "Failed to download %s: %d", resource_full_url, resp.status_code
                    )
            except Exception as ex:
                logger.error("Error downloading %s: %s", resource_full_url, ex)

        logger.info(f"Downloaded {len(downloaded_files)} files to {local_dir}")
        return downloaded_files

    except Exception as ex:
        logger.error("Exception when downloading resources: %s", ex)
        return []


async def download_bb_resources_with_login(
    local_dir: str,
    url: str | None = None,
    course_id: str | None = None,
    content_id: str | None = None,
    profile_service: ProfileService | None = None,
) -> list[str]:
    """Download Blackboard course content using CAS login.

    CAS credentials are loaded from profile settings. If *profile_service*
    is not supplied, the shared singleton is used.

    Args:
        url: The Blackboard page URL to parse for resources.
        course_id: The Blackboard course ID, e.g., "_8012_1".
        content_id: The Blackboard content ID, e.g., "_588340_1".
        local_dir: Local directory to save downloaded files.
        profile_service: Optional explicit :class:`ProfileService` instance.

    Returns:
        List of downloaded file paths.

    Raises:
        RuntimeError: If CAS login fails or credentials are missing.
    """
    if not url:
        assert course_id and content_id, (
            "url, course_id, and content_id must be provided"
        )
        url = (
            f"{BB_BASE_URL}/webapps/blackboard/content/listContent.jsp?"
            f"course_id={course_id}&content_id={content_id}"
        )

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
        logger.info("Using mock CAS credentials, skipping download")
        return []

    session = cas_login(user_name, pass_word)
    if not session:
        raise RuntimeError(
            f"CAS login failed ({user_name}, {'*' * len(pass_word)}). "
            "Please verify your CAS account/password in Settings."
        )

    session = decorate_cookies(session)

    return await asyncio.to_thread(download_bb_resources, url, local_dir, session)


def _extract_course_id_from_url(url: str) -> str | None:
    """Extract course_id parameter from a Blackboard URL.

    Args:
        url: A Blackboard URL that may contain a course_id parameter.

    Returns:
        The extracted course_id if found, otherwise None.
    """
    match = re.search(r'[?&]course_id=([^&"\']+)', url)
    if match:
        return match.group(1)
    return None


async def download_bb_resources_to_db(
    course_id: str | None = None,
    content_id: str | None = None,
    url: str | None = None,
    tags: str = "",
    description: str = "",
) -> str:
    """Download resources from a Blackboard page and save them to the database.

    Downloads files from the given course_id + content_id or from a URL and stores
    them using the CourseMaterialStore, creating course records as needed.

    Args:
        course_id: Blackboard course ID, e.g., "_8012_1".
        content_id: Blackboard content ID, e.g., "_588340_1".
        url: The Blackboard page URL to parse for resources (fallback if
            course_id and content_id are not provided).
        tags: Optional tags for the downloaded materials.
        description: Optional description for the downloaded materials.

    Returns:
        JSON string containing:
        - success (bool): Whether any files were successfully downloaded.
        - course_id (str): The course ID used.
        - course_name (str): The course name (if available).
        - materials (list): List of successfully saved materials.
        - downloaded (int): Number of files downloaded.
        - errors (list): List of error messages.
    """
    import json
    import tempfile

    from agent_core.models.course import Course
    from agent_core.persistence.course_material_provider import (
        get_course_material_store,
    )
    from agent_core.persistence.course_provider import get_course_store
    from agent_core.services.course_material_service import (
        CourseMaterialService,
        resolve_course_material_storage_root,
    )
    from agent_core.services.course_service import CourseService

    errors: list[str] = []
    materials: list[dict[str, str]] = []

    # 1. Resolve course_id and generate URL
    resolved_course_id = course_id or _extract_course_id_from_url(url)
    if not resolved_course_id:
        resolved_course_id = "blackboard"
        logger.info("No course_id found, using default: %s", resolved_course_id)

    # Generate URL from course_id + content_id if not provided
    resolved_url = url
    if not resolved_url and course_id and content_id:
        resolved_url = (
            f"{BB_BASE_URL}/webapps/blackboard/content/listContent.jsp?"
            f"course_id={course_id}&content_id={content_id}"
        )
        logger.info("Generated URL from course_id and content_id: %s", resolved_url)

    if not resolved_url:
        return json.dumps(
            {
                "success": False,
                "course_id": resolved_course_id,
                "course_name": "",
                "materials": [],
                "downloaded": 0,
                "errors": [
                    "Blackboard content URL could not be resolved. "
                    "Provide course_id with content_id, or a Blackboard URL."
                ],
            }
        )

    try:
        # 2. Get services
        profile_service = get_profile_service()
        user_name, pass_word = await profile_service.get_decrypted_profile()

        if user_name == "mock_user_name" and pass_word == "mock_pass_word":
            logger.info("Using mock CAS credentials, skipping download")
            return json.dumps(
                {
                    "success": False,
                    "course_id": resolved_course_id,
                    "course_name": "",
                    "materials": [],
                    "downloaded": 0,
                    "errors": ["Mock credentials - download skipped"],
                }
            )

        # 3. CAS login
        session = cas_login(user_name, pass_word)
        if not session:
            return json.dumps(
                {
                    "success": False,
                    "course_id": resolved_course_id,
                    "course_name": "",
                    "materials": [],
                    "downloaded": 0,
                    "errors": ["CAS login failed. Please verify your credentials."],
                }
            )

        session = decorate_cookies(session)

        # 4. Get or create course record FIRST (before download)
        course_store = await get_course_store()
        course_service = CourseService(course_store)

        existing_course = await course_store.get(resolved_course_id)
        if existing_course:
            course_name = existing_course.name
        else:
            # Try to get course name from Blackboard API
            course_name = f"Course {resolved_course_id}"
            try:
                bb_courses = await get_all_courses(profile_service)
                for bb_course in bb_courses:
                    if bb_course.get("id") == resolved_course_id:
                        course_name = bb_course.get("name", course_name)
                        break
            except Exception as e:
                logger.warning("Could not fetch course name from BB API: %s", e)

            # Create new course with the resolved course_id
            new_course = Course(
                id=resolved_course_id,
                name=course_name,
                description="Auto-created course for Blackboard materials",
            )
            created_course = await course_store.add(new_course)
            course_name = created_course.name
            logger.info("Created new course: %s (%s)", course_name, resolved_course_id)

        # 5. Download files to temp directory
        temp_dir = tempfile.mkdtemp(prefix="bb_download_")
        downloaded_files = await asyncio.to_thread(
            download_bb_resources, resolved_url, temp_dir, session
        )

        if not downloaded_files:
            return json.dumps(
                {
                    "success": False,
                    "course_id": resolved_course_id,
                    "course_name": course_name,
                    "materials": [],
                    "downloaded": 0,
                    "errors": ["No resources found or download failed."],
                }
            )

        # 6. Save files to database
        material_store = await get_course_material_store()
        material_service = CourseMaterialService(
            material_store,
            course_service,
            storage_root=str(resolve_course_material_storage_root()),
        )

        for file_path in downloaded_files:
            try:
                file_name = os.path.basename(file_path)

                # Check if material with same course_id and filename already exists
                existing_materials = await material_service.list(
                    course_id=resolved_course_id,
                )
                if any(m.filename == file_name for m in existing_materials):
                    logger.info(
                        "Skipping duplicate file: %s (already exists)",
                        file_name,
                    )
                    continue

                with open(file_path, "rb") as f:
                    file_bytes = f.read()

                # Create material record
                record = await material_service.create_from_upload(
                    course_id=resolved_course_id,
                    filename=file_name,
                    file_bytes=file_bytes,
                    description=description,
                    tags=tags,
                )

                materials.append(
                    {
                        "id": record.id,
                        "filename": record.filename,
                        "course_id": record.course_id,
                        "file_type": record.file_type,
                        "file_size": str(record.file_size),
                        "stored_path": record.stored_path,
                    }
                )
                logger.info("Saved material to DB: %s", record.filename)

            except Exception as e:
                error_msg = f"Failed to save {file_path}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # 7. Clean up temp files
        try:
            import shutil

            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Ignore cleanup errors

        return json.dumps(
            {
                "success": len(materials) > 0,
                "course_id": resolved_course_id,
                "course_name": course_name,
                "materials": materials,
                "downloaded": len(materials),
                "errors": errors,
            }
        )

    except Exception as e:
        logger.error("Exception in download_bb_resources_to_db: %s", e)
        return json.dumps(
            {
                "success": False,
                "course_id": resolved_course_id,
                "course_name": "",
                "materials": [],
                "downloaded": 0,
                "errors": [f"Unexpected error: {str(e)}"],
            }
        )


def register_blackboard_tools(registry: ToolRegistry) -> None:
    """Register all blackboard tools with the given registry.

    Called automatically by :func:`agent_core.tools.auto_discover_and_register`.
    """
    get_course_contents_desc = (
        "Get all content items (folders/files) of a specific Blackboard course. "
        "Returns a JSON list where each item has: course_id, content_id, and title. "
        "Use the course_id (e.g., '_8012_1') to identify the course. "
        "The returned content_id can be used with download_bb_resources_to_db."
    )

    @registry.register(
        description=get_course_contents_desc,
        name="get_bb_course_contents",
    )
    async def _get_bb_course_contents(course_id: str) -> str:
        import json

        contents = await get_all_contents_of_course(course_id)
        return json.dumps(contents, ensure_ascii=False)

    get_all_courses_desc = (
        "Get all enrolled Blackboard courses for the current user. "
        "Returns a JSON list where each course has: id and name. "
        "Use the course id to get its contents or download materials."
    )

    @registry.register(description=get_all_courses_desc, name="get_bb_courses")
    async def _get_bb_courses() -> str:
        import json

        courses = await get_all_courses()
        return json.dumps(courses, ensure_ascii=False)

    download_bb_desc = (
        "Download course materials from a Blackboard page and save them to the db. "
        "Fetches files from the given course_id and content_id, or from a URL. "
        "Use course_id and content_id to specify the target, or provide a URL. "
        "If course_id and content_id are provided, they take precedence. "
        "If only url is provided, extracts course_id from its course_id parameter. "
        "If the course doesn't exist, automatically creates it. "
        "Returns JSON with: success, course_id, course_name, materials, "
        "downloaded (count), and errors. Duplicate filenames are renamed."
    )

    @registry.register(
        description=download_bb_desc,
        name="download_bb_resources_to_db",
    )
    async def _download_bb_resources_to_db(
        course_id: str | None = None,
        content_id: str | None = None,
        url: str | None = None,
        tags: str = "",
        description: str = "",
    ) -> str:
        return await download_bb_resources_to_db(
            url=url,
            course_id=course_id,
            content_id=content_id,
            tags=tags,
            description=description,
        )
