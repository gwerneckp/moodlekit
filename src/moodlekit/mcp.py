"""MCP server: the same functions as the CLI, as tools for AI agents.

    pip install "pymoodlekit[mcp]"
    claude mcp add moodle -- moodle mcp

Uses the University of Bath's Moodle and your default browser unless MOODLE_URL /
MOODLE_BROWSER / MOODLE_COOKIE say otherwise. If you're not logged in, the first tool
call opens Moodle in your browser and waits for you to log in.
"""

from __future__ import annotations

from functools import wraps

from .client import Moodle, MoodleError, NotLoggedIn
from .utils import Utils


class McpServer:
    LOGIN_WAIT = 180  # seconds a tool call waits for you to log in

    def __init__(self):
        self._moodle: Moodle | None = None

    @property
    def moodle(self) -> Moodle:
        if self._moodle is None:  # created on first use, then reused
            from .cli import Cli

            self._moodle = Cli.client()
        return self._moodle

    def serve(self):
        try:
            from mcp.server.mcpserver import MCPServer
        except ImportError as e:
            raise MoodleError('The MCP server needs: pip install "pymoodlekit[mcp]" (mcp>=2)') from e

        server = MCPServer("moodle")

        def tool(fn):
            @wraps(fn)  # keep the signature and docstring: that's what the agent sees
            def wrapper(*args, **kwargs):
                try:
                    try:
                        return Utils.to_dict(fn(*args, **kwargs))
                    except NotLoggedIn:
                        if not self.moodle.browser:
                            raise
                        self.moodle.login(wait=self.LOGIN_WAIT)
                        return Utils.to_dict(fn(*args, **kwargs))
                except MoodleError as e:
                    return {"error": str(e)}
            return server.tool()(wrapper)

        @tool
        def list_courses(which: str = "inprogress"):
            """List your Moodle courses. which: inprogress | past | future | all."""
            return self.moodle.courses(which)

        @tool
        def list_activities(course: str):
            """Sections and activities (files, folders, assignments, forums...) of a course,
            by course id, shortname or part of its name. available=false: not released yet."""
            return self.moodle.activities(course)

        @tool
        def list_files(url: str):
            """The downloadable files behind an activity URL (resource, folder, page)."""
            return self.moodle.files(url)

        @tool
        def read_page(url: str):
            """Readable text and links of a Moodle page (assignment brief, forum, page...)."""
            return self.moodle.page(url)

        @tool
        def download(url: str, dest_dir: str):
            """Download the file(s) behind a URL into dest_dir. Returns the saved paths."""
            return self.moodle.download(url, dest_dir)

        @tool
        def upcoming_deadlines(days: int = 30):
            """Upcoming due dates across all courses."""
            return self.moodle.deadlines(days)

        server.run()
