"""`moodle` command line. Every command takes --json for scripts and agents."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .client import Moodle, MoodleError, NotLoggedIn
from .sync import Sync
from .utils import Utils


class Cli:
    def main(self, argv: list[str] | None = None):
        args = self._parser().parse_args(argv)
        try:
            self.run(args)
        except NotLoggedIn as e:
            sys.exit(f"Not logged in: {e}")
        except (MoodleError, ValueError) as e:
            sys.exit(f"Error: {e}")
        except KeyboardInterrupt:
            sys.exit(130)

    @staticmethod
    def client(args=None, config_path: Path | None = None) -> Moodle:
        """Build a client from flags > environment > moodle.toml."""
        config_path = config_path or Sync.find_config()
        config = Sync.load_config(config_path) if config_path else {}
        url = getattr(args, "url", None) or os.environ.get("MOODLE_URL") or config.get("url")
        cookie = getattr(args, "cookie", None) or os.environ.get("MOODLE_COOKIE")
        browser = (getattr(args, "browser", None) or os.environ.get("MOODLE_BROWSER")
                   or config.get("browser"))
        if not url:
            raise ValueError("No Moodle URL: pass --url, set MOODLE_URL, or add url to "
                             "moodle.toml")
        if cookie:
            return Moodle(url, cookie=cookie)
        return Moodle(url, browser=browser or "firefox")

    def run(self, args):
        out = Output(args.json)

        if args.command == "mcp":
            from .mcp import McpServer

            return McpServer().serve()

        if args.command == "sync":
            config_path = Path(args.config) if args.config else Sync.find_config()
            if not config_path:
                raise ValueError("No moodle.toml here or in any parent folder (see README)")
            report = Sync(self.client(args, config_path), config_path).run(
                courses=args.courses or None, dry_run=args.dry_run, mark_seen=args.mark_seen)
            if args.mark_seen:
                return out.message("Recorded everything currently on Moodle as seen.")
            return out.sync(report, args.dry_run)

        m = self.client(args)
        if args.command == "check":
            n = len(m.courses("all"))
            out.message(f"Logged in to {m.url}, {n} courses visible.", {"ok": True, "courses": n})
        elif args.command == "courses":
            out.rows(m.courses(args.which), lambda c: f"{c.id:>7}  {c.shortname:<22} {c.name}")
        elif args.command == "ls":
            out.activities(m.activities(args.course))
        elif args.command == "files":
            out.rows(m.files(args.url), lambda f: f"{f.name}\t{f.url}")
        elif args.command == "get":
            if args.pdf:
                from .render import PdfRenderer

                paths = [PdfRenderer(m).render(args.url, args.pdf)]
            else:
                paths = m.download(args.url, args.out)
            if not paths:
                raise MoodleError("No files found at that URL")
            out.rows(paths, str)
        elif args.command == "read":
            page = m.page(args.url)
            out.message(page.text + "".join(f"\n- {link['text']}: {link['url']}"
                                            for link in page.links), page)
        elif args.command == "deadlines":
            out.rows(m.deadlines(args.days),
                     lambda e: f"{e.due:%a %d %b %H:%M}  {e.course or '':<30} {e.name}")

    @staticmethod
    def _parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="moodle", description="Use Moodle from the command line with your browser login.")
        parser.add_argument("--url", help="Moodle site, e.g. https://moodle.example.ac.uk "
                                          "(or MOODLE_URL, or url in moodle.toml)")
        parser.add_argument("--browser", help="browser you're logged in with: firefox, chrome, "
                                              "edge, brave, safari... (or MOODLE_BROWSER)")
        parser.add_argument("--cookie", help="session cookie instead of a browser "
                                             "(or MOODLE_COOKIE)")
        parser.add_argument("--json", action="store_true", help="output JSON")
        sub = parser.add_subparsers(dest="command", required=True)

        sub.add_parser("check", help="check that the login works")
        p = sub.add_parser("courses", help="list your courses")
        p.add_argument("which", nargs="?", default="inprogress",
                       choices=["inprogress", "past", "future", "all"])
        p = sub.add_parser("ls", help="list a course's sections and activities")
        p.add_argument("course", help="course id, shortname or part of its name")
        p = sub.add_parser("files", help="list the files behind an activity or page URL")
        p.add_argument("url")
        p = sub.add_parser("get", help="download the file(s) behind a URL")
        p.add_argument("url")
        p.add_argument("-o", "--out", default=".", help="directory (default: current)")
        p.add_argument("--pdf", metavar="FILE",
                       help="render HTML content (e.g. HTML lecture notes) into this PDF")
        p = sub.add_parser("read", help="print the text of a Moodle page")
        p.add_argument("url")
        p = sub.add_parser("deadlines", help="upcoming due dates")
        p.add_argument("--days", type=int, default=30)
        p = sub.add_parser("sync", help="download new files for the courses in moodle.toml")
        p.add_argument("courses", nargs="*", help="only these course keys from moodle.toml")
        p.add_argument("-n", "--dry-run", action="store_true", help="only show what's new")
        p.add_argument("--mark-seen", action="store_true",
                       help="record everything as downloaded without downloading "
                            "(adopt a folder)")
        p.add_argument("--config", help="path to moodle.toml (default: search upwards)")
        sub.add_parser("mcp", help="run an MCP server (needs moodlekit[mcp])")
        return parser


class Output:
    """Prints results as text for people, or JSON with --json."""

    def __init__(self, as_json: bool):
        self.as_json = as_json

    def message(self, text, data=None):
        if self.as_json:
            self._json(data if data is not None else {"message": text})
        else:
            print(text)

    def rows(self, items, fmt):
        if self.as_json:
            return self._json(items)
        for item in items:
            print(fmt(item))
        if not items:
            print("(nothing)")

    def activities(self, acts):
        if self.as_json:
            return self._json(acts)
        section = None
        for a in acts:
            if a.section != section:
                section = a.section
                print(f"\n## {section}")
            flag = "" if a.available else "  [not available yet]"
            print(f"  {a.type:<9} {a.name}{flag}\n            {a.url}")

    def sync(self, report, dry_run):
        if self.as_json:
            return self._json(report.changes)
        labels = {"downloaded": "Would download" if dry_run else "Downloaded",
                  "updated": "Updated on Moodle" + (" (would download)" if dry_run else ""),
                  "new-activity": "New activities", "upcoming": "Listed, not released yet",
                  "skipped": "Skipped", "failed": "Failed (will retry next sync)"}
        for kind, label in labels.items():
            changes = report.of(kind)
            if changes:
                print(f"\n{label}:")
                for c in changes:
                    detail = c.path or c.note or ""
                    print(f"  [{c.course}] {c.activity}" + (f"  ->  {detail}" if detail else ""))
        if not report.changes:
            print("Nothing new.")

    def _json(self, data):
        print(json.dumps(Utils.to_dict(data), indent=1, ensure_ascii=False))


def main():
    """Console-script entry point (`moodle`)."""
    Cli().main()
