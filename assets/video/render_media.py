"""Render the README media from the HTML sources in this folder:

    demo.html   -> assets/demo.mp4, assets/demo.gif
    ../logo.svg -> assets/logo.png
    social.html -> assets/social-preview.png   (GitHub: Settings > Social preview)

    uv run --extra pdf python assets/video/render_media.py

Needs Playwright's Chromium (playwright install chromium) and ffmpeg.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


class Media:
    HERE = Path(__file__).parent
    ASSETS = HERE.parent
    FPS = 60
    GIF_FPS = 24
    GIF_WIDTH = 800
    SCALE = 1.5  # 1280x720 page -> 1920x1080 frames

    def render(self):
        if not shutil.which("ffmpeg"):
            raise SystemExit("ffmpeg is needed (brew install ffmpeg)")
        self._stills()
        with tempfile.TemporaryDirectory() as tmp:
            frames = Path(tmp)
            self._capture(frames)
            self._encode(frames)

    def _stills(self):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 512, "height": 512})
            page.goto((self.ASSETS / "logo.svg").as_uri())
            page.locator("svg").screenshot(path=str(self.ASSETS / "logo.png"), omit_background=True)
            page = browser.new_page(viewport={"width": 1280, "height": 640})
            page.goto((self.HERE / "social.html").as_uri())
            page.evaluate("window.ready")
            page.locator("#card").screenshot(path=str(self.ASSETS / "social-preview.png"))
            browser.close()
        print("logo.png, social-preview.png")

    def _capture(self, frames: Path):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720},
                                    device_scale_factor=self.SCALE)
            page.goto((self.HERE / "demo.html").as_uri())
            page.evaluate("window.ready")
            duration = page.evaluate("window.DURATION")
            stage = page.locator("#stage")
            count = round(duration * self.FPS)
            for i in range(count):
                page.evaluate(f"window.render({i / self.FPS})")
                stage.screenshot(path=str(frames / f"{i:04d}.png"))
            browser.close()
        print(f"captured {count} frames")

    def _encode(self, frames: Path):
        src = ["-framerate", str(self.FPS), "-i", str(frames / "%04d.png")]
        mp4 = self.ASSETS / "demo.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *src, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "18", "-preset", "slow", "-movflags", "+faststart", str(mp4)],
                       check=True)
        gif = self.ASSETS / "demo.gif"
        palette = (f"fps={self.GIF_FPS},scale={self.GIF_WIDTH}:-1:flags=lanczos,split[a][b];"
                   "[a]palettegen=max_colors=200:stats_mode=diff[p];"
                   "[b][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle")
        subprocess.run(["ffmpeg", "-v", "error", "-y", *src, "-vf", palette, "-loop", "0", str(gif)],
                       check=True)
        for f in (mp4, gif):
            print(f"{f.name}: {f.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    Media().render()
