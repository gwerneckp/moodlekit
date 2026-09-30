"""Moodle client that authenticates with an existing browser session.

Instead of an API token (often disabled on SSO sites), we reuse the session cookie
from a browser you're already logged in with, and talk to the same AJAX endpoint
Moodle's own web pages use. Anything the AJAX API doesn't expose is scraped from HTML.
"""

from __future__ import annotations

import html
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .browser import Browser
from .utils import Utils

LOGIN_ERRORS = {"servicerequireslogin", "invalidsesskey", "requireloginerror"}
USER_AGENT = "Mozilla/5.0 (compatible; moodlekit)"


class MoodleError(Exception):
    """Moodle returned an error."""


class NotLoggedIn(MoodleError):
    """No valid session: log in to Moodle in your browser (or pass a fresh cookie)."""


@dataclass
class Course:
    id: int
    shortname: str
    name: str
    url: str


@dataclass
class Activity:
    """Anything on a course page: a file, folder, assignment, forum, page, quiz..."""

    id: int
    name: str
    type: str  # Moodle module name: resource, folder, assign, forum, page, url, quiz, ...
    url: str | None
    section: str
    section_number: int
    available: bool  # False = listed but not released to you yet (e.g. "available from ...")
    course_id: int


@dataclass
class File:
    name: str
    url: str

    @property
    def is_html(self) -> bool:
        return self.name.lower().endswith((".html", ".htm"))


@dataclass
class Event:
    name: str
    course: str | None
    due: datetime
    url: str | None
    type: str | None


@dataclass
class Page:
    title: str
    text: str
    links: list[dict]


class Moodle:
    """A logged-in Moodle site.

    >>> m = Moodle()                      # University of Bath, your default browser
    >>> m = Moodle("moodle.example.ac.uk", browser="chrome")
    >>> m.courses()

    url:     the Moodle site (default: the University of Bath's). "https://" is optional.
    browser: read the session cookie from this browser each time it's needed
             (default: your system's default browser, if supported, else Firefox).
    cookie:  a session cookie instead, either "MoodleSessionXYZ=value" or just the value.
    """

    DEFAULT_URL = "https://moodle.bath.ac.uk"

    def __init__(self, url: str | None = None, *, browser: str | None = None,
                 cookie: str | None = None, timeout: float = 30):
        self.url = self._normalize_url(url or self.DEFAULT_URL)
        self.host = urlparse(self.url).netloc
        self.cookie = cookie
        self.browser = None if cookie else (browser or Browser.default()).lower()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._sesskey = None
        self._load_cookies(required=False)  # not logged in yet is fine: login() can fix it

    def login(self, wait: float = 300) -> None:
        """Open Moodle in your browser and wait (up to `wait` seconds) until you've logged in."""
        if not self.browser:
            raise NotLoggedIn("The session cookie you passed is invalid or expired.")
        Browser.open(self.browser, f"{self.url}/my/")
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            time.sleep(2)
            try:
                self._load_cookies()
                self.sesskey  # noqa: B018 - proves the session actually works
                return
            except NotLoggedIn:
                continue
        raise NotLoggedIn(f"Timed out waiting for you to log in to {self.url} in {self.browser}.")

    # ------------------------------------------------------------------ auth

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = url.strip().rstrip("/")
        return url if "://" in url else f"https://{url}"

    def _load_cookies(self, required: bool = True):
        if self.browser:
            try:
                cookies = Browser.cookies(self.browser, self.host)
            except ValueError:
                raise
            except Exception as e:  # locked profile, keychain denied, browser not installed...
                raise NotLoggedIn(f"Couldn't read cookies from {self.browser}: {e}") from e
        else:
            cookies = self._parse_cookie(self.cookie)
        self.session.cookies.clear()
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain=self.host, path="/")
        self._sesskey = None
        if required and not any(name.startswith("MoodleSession") for name in cookies):
            raise NotLoggedIn(self._login_hint())

    def _login_hint(self) -> str:
        if self.browser:
            return f"Not logged in to {self.url} in {self.browser}."
        return "The session cookie you passed is invalid or expired."

    def _parse_cookie(self, cookie: str) -> dict:
        if "=" in cookie:
            pairs = (p.strip().split("=", 1) for p in cookie.split(";") if "=" in p)
            return {k: v for k, v in pairs}
        # Just a value: the cookie name is "MoodleSession" + a site-specific suffix.
        r = requests.get(f"{self.url}/login/index.php", timeout=self.timeout,
                         headers={"User-Agent": USER_AGENT})
        names = [c.name for c in r.cookies if c.name.startswith("MoodleSession")]
        return {names[0] if names else "MoodleSession": cookie}

    def _relogin_or_raise(self, retry: bool):
        if retry and self.browser:
            self._load_cookies()  # the browser may hold a fresher session
            return
        raise NotLoggedIn(self._login_hint())

    @property
    def sesskey(self) -> str:
        if not self._sesskey:
            text = self.get("/my/").text
            m = re.search(r'"sesskey":"([^"]+)"', text)
            if not m:
                raise NotLoggedIn(f"Couldn't find a sesskey: are you logged in to {self.url}?")
            self._sesskey = m[1]
        return self._sesskey

    # ------------------------------------------------------------- low level

    def get(self, url: str, **kw) -> requests.Response:
        """GET a Moodle URL (absolute or site-relative) with the session."""
        return self._request("GET", url, **kw)

    def _request(self, method, url, _retry=True, **kw) -> requests.Response:
        if not url.startswith("http"):
            url = f"{self.url}/{url.lstrip('/')}"
        r = self.session.request(method, url, timeout=self.timeout, **kw)
        if self._is_login_redirect(r):
            self._relogin_or_raise(_retry)
            return self._request(method, url, _retry=False, **kw)
        r.raise_for_status()
        return r

    @staticmethod
    def _is_login_redirect(r: requests.Response) -> bool:
        urls = [r.url, r.headers.get("location", "")] + [h.url for h in r.history]
        return any("/login/index.php" in u for u in urls)

    def call(self, method: str, _retry: bool = True, **args):
        """Call a Moodle web service function through the AJAX endpoint.

        Only functions marked AJAX-enabled work this way (most of what the web UI uses).
        """
        r = self._request("POST", "/lib/ajax/service.php",
                          params={"sesskey": self.sesskey, "info": method},
                          json=[{"index": 0, "methodname": method, "args": args}])
        res = r.json()
        res = res[0] if isinstance(res, list) else res
        if not res.get("error"):
            return res["data"]
        exc = res.get("exception") or res
        if exc.get("errorcode") in LOGIN_ERRORS:
            self._relogin_or_raise(_retry)
            return self.call(method, _retry=False, **args)
        raise MoodleError(f"{method}: {exc.get('message') or exc}")

    # ------------------------------------------------------------ high level

    def courses(self, classification: str = "inprogress") -> list[Course]:
        """Your courses. classification: inprogress | past | future | all."""
        data = self.call("core_course_get_enrolled_courses_by_timeline_classification",
                         offset=0, limit=0, classification=classification, sort="fullname")
        return [Course(id=c["id"], shortname=html.unescape(c["shortname"]).strip(),
                       name=html.unescape(c["fullname"]).strip(), url=c["viewurl"])
                for c in data["courses"]]

    def course(self, key: Course | int | str) -> Course:
        """Find one of your courses by id, shortname or part of its name."""
        if isinstance(key, Course):
            return key
        courses = self.courses("all")
        k = str(key).strip().lower()
        exact = [c for c in courses if str(c.id) == k or c.shortname.lower() == k]
        if exact:
            return exact[0]
        matches = [c for c in courses if k in c.shortname.lower() or k in c.name.lower()]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise MoodleError(f"No course matches {key!r}")
        names = ", ".join(f"{c.shortname} ({c.id})" for c in matches)
        raise MoodleError(f"{key!r} matches several courses: {names}")

    def activities(self, course: Course | int | str) -> list[Activity]:
        """Everything on a course page, in order. Includes items not released yet
        (available=False) so you can see what's coming."""
        course = self.course(course)
        try:
            state = json.loads(self.call("core_courseformat_get_state", courseid=course.id))
        except NotLoggedIn:
            raise
        except MoodleError:  # Moodle < 4.0 has no course format state: scrape instead
            return self._activities_from_html(course)
        cms = {str(cm["id"]): cm for cm in state["cm"]}
        out = []
        for sec in sorted(state["section"], key=lambda s: s["number"]):
            for cmid in sec.get("cmlist", []):
                cm = cms.get(str(cmid))
                if not cm or not cm.get("url") or cm.get("module") == "subsection":
                    continue  # labels (text only) and subsection containers
                out.append(Activity(
                    id=int(cm["id"]), name=html.unescape(cm["name"]).strip(),
                    type=cm.get("module", ""), url=cm["url"],
                    section=html.unescape(sec["title"]).strip(), section_number=sec["number"],
                    available=bool(cm.get("uservisible", True)), course_id=course.id))
        return out

    def _activities_from_html(self, course: Course) -> list[Activity]:
        soup = BeautifulSoup(self.get(f"/course/view.php?id={course.id}").text, "html.parser")
        out = []
        for n, sec in enumerate(soup.select("li.section")):
            title = sec.select_one(".sectionname")
            seen = set()
            for a in sec.select("a[href*='/mod/']"):
                m = re.search(r"/mod/(\w+)/view\.php\?id=(\d+)", a["href"])
                if not m or m[2] in seen:
                    continue
                seen.add(m[2])
                name = a.select_one(".instancename") or a
                for hidden in name.select(".accesshide"):
                    hidden.decompose()
                out.append(Activity(
                    id=int(m[2]), name=name.get_text(" ", strip=True), type=m[1],
                    url=urljoin(self.url, a["href"]),
                    section=title.get_text(" ", strip=True) if title else "",
                    section_number=n, available=True, course_id=course.id))
        return out

    def files(self, target: Activity | File | str) -> list[File]:
        """The file(s) behind a resource, folder, pluginfile link or any page with files."""
        if isinstance(target, File):
            return [target]
        url = target.url if isinstance(target, Activity) else target
        if not url:
            return []
        if "pluginfile.php" in url:
            return [File(self._filename(url), url)]
        r = self.get(url, allow_redirects=False)
        if r.is_redirect:
            loc = urljoin(url, r.headers.get("location", ""))
            return [File(self._filename(loc), loc)] if "pluginfile.php" in loc else []
        soup = BeautifulSoup(r.text, "html.parser")
        main = soup.select_one("#region-main") or soup
        found = []
        for el in main.select("a[href], object[data], iframe[src], embed[src]"):
            u = el.get("href") or el.get("data") or el.get("src")
            if u and "pluginfile.php" in u:
                u = urljoin(url, u)
                if u not in (f.url for f in found):
                    found.append(File(self._filename(u), u))
        return found

    @staticmethod
    def _filename(url: str) -> str:
        return unquote(Path(urlparse(url).path).name) or "download"

    def save(self, file: File | str, path: str | Path) -> Path:
        """Download one file to exactly `path` (parents are created)."""
        url = file.url if isinstance(file, File) else file
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.get(url, stream=True) as r:  # follows redirects (e.g. to S3)
            tmp = path.with_name(path.name + ".part")
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 16):
                    fh.write(chunk)
            tmp.replace(path)
        return path

    def download(self, target: Activity | File | str, dest: str | Path = ".") -> list[Path]:
        """Download the file(s) behind target into directory `dest`. Never overwrites:
        an existing name gets a " (1)" suffix."""
        return [self.save(f, Utils.unique_path(Path(dest).expanduser() / f.name))
                for f in self.files(target)]

    def page(self, url: str) -> Page:
        """Readable text of a Moodle page (assignment brief, page, forum post...) plus
        the file and activity links on it."""
        soup = BeautifulSoup(self.get(url).text, "html.parser")
        main = soup.select_one("#region-main") or soup.body or soup
        for tag in main.select("script, style, nav"):
            tag.decompose()
        links = [{"text": a.get_text(" ", strip=True), "url": urljoin(url, a["href"])}
                 for a in main.select("a[href]")
                 if "pluginfile.php" in a["href"] or "/mod/" in a["href"]]
        text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
        title = soup.title.get_text(strip=True) if soup.title else ""
        return Page(title=title, text=text, links=links)

    def deadlines(self, days: int = 30) -> list[Event]:
        """Upcoming things with a due date (assignments, quizzes...) across all courses."""
        now = int(time.time())
        data = self.call("core_calendar_get_action_events_by_timesort",
                         timesortfrom=now, timesortto=now + days * 86400, limitnum=50)
        return [Event(name=html.unescape(e["name"]),
                      course=html.unescape((e.get("course") or {}).get("fullname") or "") or None,
                      due=datetime.fromtimestamp(e["timesort"]), url=e.get("url"),
                      type=e.get("modulename"))
                for e in data["events"]]


