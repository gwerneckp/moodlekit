"""Render HTML material (e.g. lecture notes published as a multi-page HTML book) to one PDF.

Needs the optional extra:  pip install "moodlekit[pdf]"  &&  playwright install chromium
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .client import Activity, File, Moodle, MoodleError


class PdfRenderer:
    """>>> PdfRenderer(moodle).render("https://.../mod/resource/view.php?id=1", "notes.pdf")"""

    def __init__(self, moodle: Moodle):
        self.moodle = moodle

    def render(self, target: Activity | File | str, path: str | Path) -> Path:
        """Print an HTML page, plus the pages it links to in the same folder (chapters),
        into a single PDF at `path`."""
        try:
            from playwright.sync_api import sync_playwright
            from pypdf import PdfWriter
        except ImportError as e:
            raise MoodleError('HTML to PDF needs: pip install "moodlekit[pdf]" && '
                              "playwright install chromium") from e

        index = self._index_url(target)
        pages = [index]
        for href in re.findall(r'href="([^"#?]+\.html?)"', self.moodle.get(index).text):
            url = urljoin(index, href)
            if self._same_folder(url, index) and url not in pages:
                pages.append(url)

        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        writer = PdfWriter()
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:
                raise MoodleError("Playwright's browser isn't installed: "
                                  "run `playwright install chromium`") from e
            ctx = browser.new_context()
            ctx.add_cookies([{"name": c.name, "value": c.value, "domain": self.moodle.host,
                              "path": "/"} for c in self.moodle.session.cookies])
            page = ctx.new_page()
            for i, url in enumerate(pages):
                page.goto(url)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(500)  # let MathJax/KaTeX finish typesetting
                part = Path(tmp) / f"{i:03d}.pdf"
                page.pdf(path=str(part), format="A4", print_background=True,
                         margin={"top": "15mm", "bottom": "15mm", "left": "12mm",
                                 "right": "12mm"})
                writer.append(str(part))
            browser.close()
            writer.write(str(path))
        return path

    def _index_url(self, target) -> str:
        files = [f for f in self.moodle.files(target) if f.is_html]
        if not files:
            raise MoodleError(f"No HTML content found behind {target}")
        return files[0].url

    @staticmethod
    def _same_folder(url: str, index: str) -> bool:
        a, b = urlparse(url), urlparse(index)
        return a.netloc == b.netloc and a.path.rsplit("/", 1)[0] == b.path.rsplit("/", 1)[0]
