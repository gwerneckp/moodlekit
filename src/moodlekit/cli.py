"""`moodle` command line. Every command takes --json for scripts and agents."""

from __future__ import annotations

import argparse
import json
import os
import sys

from .client import Moodle, MoodleError, NotLoggedIn
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
    def client(args=None) -> Moodle:
        """Build a client from flags > environment > defaults (Bath, your default browser)."""
        url = getattr(args, "url", None) or os.environ.get("MOODLE_URL")
        cookie = getattr(args, "cookie", None) or os.environ.get("MOODLE_COOKIE")
        browser = getattr(args, "browser", None) or os.environ.get("MOODLE_BROWSER")
        return Moodle(url, browser=browser, cookie=cookie)

    def run(self, args):
        if args.command == "mcp":
            from .mcp import McpServer

            return McpServer().serve()

        m = self.client(args)
        try:
            self._dispatch(args, m)
        except NotLoggedIn:
            if not m.browser:
                raise
            print(f"Not logged in to {m.url}. Opening it in {m.browser}: log in there and "
                  "I'll carry on automatically...", file=sys.stderr, flush=True)
            m.login()
            print("Logged in.", file=sys.stderr, flush=True)
            self._dispatch(args, m)

    def _dispatch(self, args, m: Moodle):
        out = Output(args.json)
        if args.command == "check":
            n = len(m.courses("all"))
            how = m.browser or "a cookie"
            out.message(f"Logged in to {m.url} with {how}, {n} courses visible.",
                        {"ok": True, "url": m.url, "browser": m.browser, "courses": n})
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
        parser.add_argument("--url", help=f"Moodle site (default: {Moodle.DEFAULT_URL}, "
                                          "or MOODLE_URL)")
        parser.add_argument("--browser", help="browser you're logged in with: firefox, chrome, "
                                              "safari, edge, brave, arc... (default: your system "
                                              "default, or MOODLE_BROWSER)")
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

    def _json(self, data):
        print(json.dumps(Utils.to_dict(data), indent=1, ensure_ascii=False))


def main():
    """Console-script entry point (`moodle`)."""
    Cli().main()
