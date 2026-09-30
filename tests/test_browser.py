"""Default-browser detection (no real browser needed)."""

import plistlib
import subprocess

from moodlekit import Browser


def test_default_browser_on_macos(monkeypatch, tmp_path):
    prefs = tmp_path / "Library/Preferences/com.apple.LaunchServices"
    prefs.mkdir(parents=True)
    (prefs / "com.apple.launchservices.secure.plist").write_bytes(plistlib.dumps({"LSHandlers": [
        {"LSHandlerURLScheme": "mailto", "LSHandlerRoleAll": "com.apple.mail"},
        {"LSHandlerURLScheme": "https", "LSHandlerRoleAll": "com.google.chrome"},
    ]}))
    monkeypatch.setattr("moodlekit.browser.sys.platform", "darwin")
    monkeypatch.setattr("moodlekit.browser.Path.home", lambda: tmp_path)
    assert Browser.default() == "chrome"


def test_default_browser_on_linux(monkeypatch):
    monkeypatch.setattr("moodlekit.browser.sys.platform", "linux")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a, 0, stdout="brave-browser.desktop\n"))
    assert Browser.default() == "brave"


def test_unsupported_or_unknown_default_falls_back_to_firefox(monkeypatch):
    monkeypatch.setattr("moodlekit.browser.sys.platform", "linux")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a, 0, stdout="some-other-browser.desktop\n"))
    assert Browser.default() == "firefox"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert Browser.default() == "firefox"


def test_unsupported_browser_name_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="Unsupported browser"):
        Browser.cookies("netscape", "moodle.test")
