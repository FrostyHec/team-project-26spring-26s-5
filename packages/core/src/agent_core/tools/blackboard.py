import html
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import threading
import warnings
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import requests
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

SUCCESS = "[\x1b[0;32m+\x1b[0m] "
ERROR = "[\x1b[0;31mx\x1b[0m] "
INFO = "[\x1b[0;36m!\x1b[0m] "
FAIL = "[\x1b[0;33m-\x1b[0m] "

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"user-agent": UA, "x-requested-with": "XMLHttpRequest"}
HEADERS_BB = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9",
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


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _is_wsl() -> bool:
    if os.getenv("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version", encoding="utf-8") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False


def _open_browser_url(url: str) -> bool:
    """Open URL with robust fallback for WSL/headless environments."""
    try:
        if webbrowser.open(url):
            return True
    except Exception:
        pass

    # WSL fallback: open in Windows default browser.
    if _is_wsl():
        if shutil.which("wslview"):
            try:
                subprocess.run(
                    ["wslview", url],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                pass
        if shutil.which("cmd.exe"):
            try:
                subprocess.run(
                    ["cmd.exe", "/c", "start", "", url],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                pass

    # Generic Linux fallback if xdg-open exists.
    if shutil.which("xdg-open"):
        try:
            subprocess.run(
                ["xdg-open", url],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            pass

    return False


def _prompt_credentials_via_browser(attempt_index: int) -> tuple[str, str] | None:
    """Collect CAS credentials from a temporary local browser popup.

    A minimal one-shot HTTP server serves a login form and receives POSTed
    credentials. Returns ``None`` if the user cancels or times out.
    """
    result_queue: queue.Queue[tuple[str, str] | None] = queue.Queue(maxsize=1)
    port = _find_free_port()
    title = f"Blackboard CAS Login (Attempt {attempt_index})"

    class _CredHandler(BaseHTTPRequestHandler):
        def _write_html(self, body: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/":
                page = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{
      font-family: "Segoe UI", Tahoma, sans-serif;
      margin: 2rem;
      background: #f6f8fa;
    }}
    .card {{
      max-width: 460px;
      margin: 0 auto;
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 1.2rem;
    }}
    h1 {{ font-size: 1.1rem; margin: 0 0 0.8rem; }}
    p {{ color: #374151; font-size: 0.9rem; }}
    label {{ display: block; margin-top: 0.8rem; font-size: 0.9rem; }}
    input {{
      width: 100%;
      box-sizing: border-box;
      margin-top: 0.35rem;
      padding: 0.6rem 0.7rem;
      border: 1px solid #d1d5db;
      border-radius: 8px;
    }}
    .row {{ display: flex; gap: 0.6rem; margin-top: 1rem; }}
    button {{
      border: 0;
      border-radius: 8px;
      padding: 0.6rem 0.9rem;
      cursor: pointer;
    }}
    .ok {{ background: #2563eb; color: #fff; }}
    .cancel {{ background: #e5e7eb; color: #111827; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{title}</h1>
    <p>
      Please enter your student ID and CAS password.
      You can close this window after submission.
    </p>
    <form method="post" action="/submit">
      <label>
        Student ID
        <input name="username" autocomplete="username" required />
      </label>
      <label>
        CAS Password
        <input
          type="password"
          name="password"
          autocomplete="current-password"
          required
        />
      </label>
      <div class="row">
        <button class="ok" type="submit">Submit</button>
        <button
          class="cancel"
          type="button"
          onclick="location.href='/cancel'"
        >
          Cancel
        </button>
      </div>
    </form>
  </div>
</body>
</html>
""".format(title=html.escape(title))
                self._write_html(page)
                return

            if self.path == "/cancel":
                if result_queue.empty():
                    result_queue.put(None)
                self._write_html("<h3>Cancelled. You can close this window now.</h3>")
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return

            self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/submit":
                self.send_error(404)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length).decode("utf-8", errors="ignore")
            form = parse_qs(raw)
            username = (form.get("username", [""])[0] or "").strip()
            password = form.get("password", [""])[0] or ""

            if not username or not password:
                self._write_html(
                    "<h3>Username/password cannot be empty. "
                    "Please go back and retry.</h3>",
                    status=400,
                )
                return

            if result_queue.empty():
                result_queue.put((username, password))
            self._write_html(
                "<h3>Submitted. You can close this window and return to the app.</h3>"
            )
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, _format: str, *_args: object) -> None:
            # Keep CLI/API logs clean.
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), _CredHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    url = f"http://127.0.0.1:{port}/"
    localhost_url = f"http://localhost:{port}/"
    print(INFO + f"Opening browser popup for Blackboard login: {url}")
    opened = _open_browser_url(url)
    if not opened:
        print(
            FAIL
            + "Could not auto-open browser. Please open this URL manually: "
            + localhost_url
        )

    try:
        return result_queue.get(timeout=180)
    except queue.Empty:
        print(ERROR + "Credential input timed out.")
        return None
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
        server.server_close()


def cas_login(sid, pwd):
    """
    Reuse CAS login logic to obtain valid cookies for accessing Blackboard
    :param sid: Student ID
    :param pwd: CAS password
    :return: Logged-in Session object, returns None on failure
    """
    session = requests.Session()
    session.verify = False
    session.headers.update(HEADERS)

    try:
        login_url = (
            "https://cas.sustech.edu.cn/cas/login?"
            "service=https%3A%2F%2Fbb.sustech.edu.cn/"
        )
        req = session.get(login_url)
        assert req.status_code == 200
    except Exception as ex:
        print(ERROR + f"Cannot access CAS, please check network connection ({ex})")
        return None

    try:
        execution = re.findall(r'''name="execution" value="(.+?)"''', req.text)[0]
    except IndexError:
        print(ERROR + "Failed to extract CAS execution parameter")
        return None

    data = {
        "username": sid,
        "password": pwd,
        "execution": execution,
        "_eventId": "submit",
        "geolocation": "",
    }

    try:
        req = session.post(login_url, data=data, allow_redirects=False)
        if req.status_code == 500:
            print(ERROR + "CAS service internal error")
            return None

        if "Location" not in req.headers:
            print(ERROR + "Invalid username or password")
            return None

        resp = session.get(req.headers["Location"], allow_redirects=True)
        session.get(f"{BB_BASE_URL}/learn/", headers=HEADERS_BB)
        if "bb" in resp.url and resp.status_code == 200:
            print(SUCCESS + "CAS login successful, Blackboard session established")
            return session
        else:
            print(ERROR + "CAS login failed to redirect to Blackboard")
            return None
    except Exception as ex:
        print(ERROR + f"CAS login exception: {ex}")
        return None


def get_bb_courses(session):
    try:
        url = f"{BB_API_ENDPOINT}/calendars"
        resp = session.get(url, headers={**HEADERS_BB, "Referer": f"{BB_BASE_URL}/"})

        if resp.status_code != 200:
            print(
                ERROR + f"Failed to get course list: {resp.status_code} - {resp.text}"
            )
            return []

        data = resp.json()
        if not data.get("results"):
            return []

        courses = [_ for _ in data["results"] if _["id"].startswith("_")]
        print(SUCCESS + f"Retrieved {len(courses)} courses")
        return courses
    except Exception as ex:
        print(ERROR + f"Exception when getting course list: {ex}")
        return []


def get_course_ddls(session, course_id):
    """
    Get all deadlines (assignments, quizzes, due dates, etc.) for a single course
    :param session: Logged-in Session object
    :param course_id: Course ID
    :return: List of deadlines for the course
    """
    try:
        url = f"{BB_API_ENDPOINT_V2}/courses/{course_id}/gradebook/columns"
        resp = session.get(url, headers={**HEADERS_BB, "Referer": f"{BB_BASE_URL}/"})

        if resp.status_code != 200:
            print(
                ERROR + f"Failed to get course grades: {resp.status_code} - {resp.text}"
            )
            return []

        data = resp.json()
        if not data.get("results"):
            return []

        ddls = []
        for item in data["results"]:
            if "name" in item and "grading" in item and "due" in item["grading"]:
                ddls.append({"title": item["name"], "dueDate": item["grading"]["due"]})
        return ddls
    except Exception as ex:
        print(ERROR + f"Exception when getting course grades: {ex}")
        return []


def decorate_cookies(session):
    session.cookies.set("COOKIE_CONSENT_ACCEPTED", "true", domain="bb.sustech.edu.cn")
    session.cookies.set("CdnSignedValidation", "false", domain="bb.sustech.edu.cn")
    session.cookies.set(
        "BbClientCalenderTimeZone", "Asia/Shanghai", domain="bb.sustech.edu.cn"
    )
    session.cookies.set(
        "BbClientDownloadExecuting", "false", domain="bb.sustech.edu.cn"
    )
    return session


def get_all_ddls():
    """
    Get all deadlines for all courses.

    Always tries CAS login first (with browser credential popup). If CAS login
    fails 3 times, falls back to cached JSON.
    :return: Dictionary of all courses' deadlines
    """
    # Try to login with CAS (max 3 attempts)
    session = None
    attempt_count = 0
    max_attempts = 3

    while not session and attempt_count < max_attempts:
        credentials = _prompt_credentials_via_browser(attempt_count + 1)
        if credentials is None:
            print(FAIL + "Credential input cancelled or timed out.")
            attempt_count += 1
            continue

        user_name, pass_word = credentials
        session = cas_login(user_name, pass_word)
        attempt_count += 1

        if not session:
            msg = (
                f"Login failed (attempt {attempt_count}/{max_attempts}), "
                "please try again..."
            )
            print(FAIL + msg)

    # If login failed after all attempts, try to load from cached data
    if not session:
        print(
            INFO
            + "CAS login failed after maximum attempts. Trying to load cached data..."
        )
        if os.path.exists("bb_cached_ddls.json"):
            try:
                cached_data = json.load(open("bb_cached_ddls.json"))
                print(SUCCESS + "Loaded cached data successfully")
                return cached_data
            except Exception as e:
                print(ERROR + f"Failed to load cached data: {e}")
                return {}
        else:
            print(ERROR + "No cached data available")
            return {}

    # If login successful, fetch data and save to cache
    session = decorate_cookies(session)
    courses = get_bb_courses(session)
    all_ddls = {}
    for course in courses:
        all_ddls[course["name"]] = get_course_ddls(session, course["id"])

    # Save to cache
    try:
        with open("bb_cached_ddls.json", "w", encoding="utf-8") as f:
            json.dump(all_ddls, f, ensure_ascii=False, indent=4)
        print(SUCCESS + "Saved data to cache successfully")
    except Exception as e:
        print(ERROR + f"Failed to save data to cache: {e}")

    return all_ddls


if __name__ == "__main__":
    get_all_ddls()
