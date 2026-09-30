"""Mirror Moodle courses into local folders and report what's new.

A `moodle.toml` in your folder says which courses go where:

    url = "https://moodle.example.ac.uk"
    browser = "firefox"
    exclude = ["*(html)*"]            # activity-name globs to skip, for every course
    layout = "{section}/{filename}"   # where files land inside a course folder

    [courses.MA22038]                 # shortname, id, or part of the course name
    path = "Year_2/Semester_1/Probabilistic_Modelling_MA22038"

A `.moodle-state.json` next to it remembers what was downloaded (by file URL, which
includes Moodle's revision number). So you can move or rename files freely without
them being downloaded again, and a file the lecturer re-uploads shows up as "updated".
"""

from __future__ import annotations

import fnmatch
import json
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .client import File, Moodle, NotLoggedIn
from .utils import Utils


@dataclass
class Change:
    course: str
    activity: str
    kind: str  # downloaded | updated | new-activity | upcoming | skipped | failed
    path: str | None = None
    url: str | None = None
    note: str | None = None


@dataclass
class SyncReport:
    changes: list[Change] = field(default_factory=list)

    def of(self, kind: str) -> list[Change]:
        return [c for c in self.changes if c.kind == kind]


class Sync:
    """Download new/updated files for the courses in a moodle.toml.

    >>> Sync(moodle, "moodle.toml").run(dry_run=True).changes
    """

    CONFIG_NAME = "moodle.toml"
    STATE_NAME = ".moodle-state.json"
    FILE_TYPES = {"resource", "folder"}
    DEFAULT_LAYOUT = "{section}/{filename}"

    def __init__(self, moodle: Moodle, config_path: str | Path):
        self.moodle = moodle
        self.config_path = Path(config_path).resolve()
        self.root = self.config_path.parent
        self.config = self.load_config(self.config_path)
        self.state_path = self.root / self.STATE_NAME

    @classmethod
    def find_config(cls, start: str | Path = ".") -> Path | None:
        """Look for moodle.toml in `start` and its parents (like git does)."""
        start = Path(start).resolve()
        for d in [start, *start.parents]:
            if (d / cls.CONFIG_NAME).is_file():
                return d / cls.CONFIG_NAME
        return None

    @staticmethod
    def load_config(path: str | Path) -> dict:
        with open(path, "rb") as fh:
            return tomllib.load(fh)

    def run(self, *, courses: list[str] | None = None, dry_run: bool = False,
            mark_seen: bool = False, render_html: bool | None = None) -> SyncReport:
        """dry_run:   only report what would happen ("has anything been published?").
        mark_seen: record everything currently on Moodle as already downloaded, without
                   downloading. Use once when adopting a folder you've filled by hand.
        courses:   only sync these config keys.
        """
        state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        known_files: dict = state.setdefault("files", {})
        known_activities: list = state.setdefault("activities", [])
        if render_html is None:
            render_html = bool(self.config.get("render_html", False))

        report = SyncReport()
        for key, conf in self.config.get("courses", {}).items():
            if courses and key not in courses:
                continue
            course = self.moodle.course(conf.get("course", key))
            course_dir = self.root / conf["path"]
            layout = conf.get("layout", self.config.get("layout", self.DEFAULT_LAYOUT))
            exclude = [*self.config.get("exclude", []), *conf.get("exclude", [])]

            for act in self.moodle.activities(course):
                if any(fnmatch.fnmatch(act.name.lower(), g.lower()) for g in exclude):
                    continue
                if not act.available:
                    report.changes.append(Change(key, act.name, "upcoming", url=act.url))
                    continue
                if act.id not in known_activities:
                    if act.type not in self.FILE_TYPES:
                        report.changes.append(Change(key, act.name, "new-activity",
                                                     url=act.url, note=act.type))
                    if not dry_run:
                        known_activities.append(act.id)
                if act.type not in self.FILE_TYPES:
                    continue

                for f in self.moodle.files(act):
                    if f.url in known_files:
                        continue
                    updated = any(v.get("activity") == act.id and v.get("name") == f.name
                                  for v in known_files.values())
                    name = f.name
                    if f.is_html:
                        if not render_html:
                            report.changes.append(Change(key, act.name, "skipped", url=f.url,
                                                         note="HTML content; enable render_html"))
                            continue
                        name = f"{act.name}.pdf"
                    safe = Utils.safe_name
                    rel = layout.format(section=safe(act.section) or "General",
                                        activity=safe(act.name), filename=safe(name),
                                        course=safe(course.shortname))
                    path = course_dir / rel
                    if not dry_run and not mark_seen:
                        path = Utils.unique_path(path)
                        try:
                            self._fetch(f, path)
                        except NotLoggedIn:
                            raise
                        except Exception as e:  # report, don't record: retried next sync
                            report.changes.append(Change(key, act.name, "failed", url=f.url,
                                                         note=str(e).splitlines()[0]))
                            continue
                    rel_path = str(path.relative_to(self.root))
                    if not dry_run:
                        known_files[f.url] = {"activity": act.id, "name": f.name,
                                              "path": rel_path,
                                              "at": datetime.now().isoformat(timespec="seconds")}
                    if not mark_seen:
                        report.changes.append(Change(key, act.name,
                                                     "updated" if updated else "downloaded",
                                                     path=rel_path, url=f.url))

            if not dry_run:  # save after each course so an interruption loses little
                self.state_path.write_text(json.dumps(state, indent=1))
        return report

    def _fetch(self, f: File, path: Path):
        if f.is_html:
            from .render import PdfRenderer

            PdfRenderer(self.moodle).render(f, path)
        else:
            self.moodle.save(f, path)

