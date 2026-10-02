"""The browser you're logged in with: find the default one, read its cookies, open pages in it."""

from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
import webbrowser
from pathlib import Path


class Browser:
    """Browsers we can read cookies from (via browser-cookie3), with how to spot and open them.

    name: (macOS bundle id, Linux .desktop prefixes, Windows ProgId prefixes)
    """

    SUPPORTED = {
        "firefox": ("org.mozilla.firefox", ("firefox",), ("FirefoxURL",)),
        "chrome": ("com.google.Chrome", ("google-chrome",), ("ChromeHTML",)),
        "safari": ("com.apple.Safari", (), ()),
        "edge": ("com.microsoft.edgemac", ("microsoft-edge",), ("MSEdgeHTM",)),
        "brave": ("com.brave.Browser", ("brave-browser", "brave"), ("BraveHTML",)),
        "arc": ("company.thebrowser.Browser", (), ()),
        "chromium": ("org.chromium.Chromium", ("chromium",), ("ChromiumHTM",)),
        "opera": ("com.operasoftware.Opera", ("opera",), ("OperaStable",)),
        "vivaldi": ("com.vivaldi.Vivaldi", ("vivaldi",), ("VivaldiHTM",)),
        "librewolf": ("io.gitlab.librewolf-community", ("librewolf",), ("LibreWolfHTM",)),
    }
    FALLBACK = "firefox"

    # User data dir per OS, keyed by browser name (for resolving the last-used profile).
    CHROMIUM_USER_DATA_DIRS = {
        "chrome": ("~/Library/Application Support/Google/Chrome",
                   "~/.config/google-chrome", "Google/Chrome/User Data"),
        "edge": ("~/Library/Application Support/Microsoft Edge",
                 "~/.config/microsoft-edge", "Microsoft/Edge/User Data"),
        "brave": ("~/Library/Application Support/BraveSoftware/Brave-Browser",
                  "~/.config/BraveSoftware/Brave-Browser", "BraveSoftware/Brave-Browser/User Data"),
        "chromium": ("~/Library/Application Support/Chromium",
                     "~/.config/chromium", "Chromium/User Data"),
        "vivaldi": ("~/Library/Application Support/Vivaldi",
                    "~/.config/vivaldi", "Vivaldi/User Data"),
        "arc": ("~/Library/Application Support/Arc/User Data", None, None),
    }

    @classmethod
    def default(cls) -> str:
        """The system's default browser if we support it, else Firefox."""
        try:
            if sys.platform == "darwin":
                name = cls._default_macos()
            elif sys.platform.startswith("win"):
                name = cls._default_windows()
            else:
                name = cls._default_linux()
        except Exception:
            name = None
        return name or cls.FALLBACK

    @classmethod
    def cookies(cls, name: str, host: str) -> dict:
        """Cookies for `host` from browser `name`."""
        import browser_cookie3

        name = name.lower()
        loader = getattr(browser_cookie3, name, None) if name in cls.SUPPORTED else None
        if loader is None:
            raise ValueError(f"Unsupported browser {name!r}. Supported: {', '.join(cls.SUPPORTED)}")
        jar = loader(cookie_file=cls._chromium_cookie_file(name), domain_name=host)
        return {c.name: c.value for c in jar if c.domain.lstrip(".") in host}

    @classmethod
    def _chromium_cookie_file(cls, name: str) -> str | None:
        """The Cookies file of the last-used Chromium profile, or None to defer to the default."""
        dirs = cls.CHROMIUM_USER_DATA_DIRS.get(name)
        if not dirs:
            return None
        mac, linux, windows = dirs
        if sys.platform == "darwin":
            base = mac
        elif sys.platform.startswith("win"):
            base = windows and os.path.join(os.environ.get("LOCALAPPDATA", ""), windows)
        else:
            base = linux
        if not base:
            return None
        base = Path(base).expanduser()
        try:
            state = json.loads((base / "Local State").read_text(encoding="utf-8"))
            profile = state["profile"]["last_used"]
        except (OSError, ValueError, KeyError):
            return None
        cookie_file = base / profile / "Cookies"
        return str(cookie_file) if cookie_file.exists() else None

    @classmethod
    def open(cls, name: str, url: str):
        """Open `url` in browser `name` (falls back to the system default)."""
        bundle = cls.SUPPORTED.get(name.lower(), ("",))[0]
        if sys.platform == "darwin" and bundle:
            if subprocess.run(["open", "-b", bundle, url], capture_output=True).returncode == 0:
                return
        try:
            webbrowser.get(name).open(url)
        except webbrowser.Error:
            webbrowser.open(url)

    @classmethod
    def _default_macos(cls) -> str | None:
        prefs = (Path.home() / "Library/Preferences/com.apple.LaunchServices"
                 / "com.apple.launchservices.secure.plist")
        handlers = plistlib.loads(prefs.read_bytes()).get("LSHandlers", [])
        bundle = next((h.get("LSHandlerRoleAll", "") for h in handlers
                       if h.get("LSHandlerURLScheme") == "https"), "").lower()
        return next((n for n, (b, _, _) in cls.SUPPORTED.items() if b.lower() == bundle), None)

    @classmethod
    def _default_linux(cls) -> str | None:
        desktop = subprocess.run(["xdg-settings", "get", "default-web-browser"],
                                 capture_output=True, text=True).stdout.strip().lower()
        return next((n for n, (_, prefixes, _) in cls.SUPPORTED.items()
                     if any(desktop.startswith(p) for p in prefixes)), None)

    @classmethod
    def _default_windows(cls) -> str | None:
        import winreg

        key = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            prog_id = winreg.QueryValueEx(k, "ProgId")[0]
        return next((n for n, (_, _, ids) in cls.SUPPORTED.items()
                     if any(prog_id.startswith(i) for i in ids)), None)
