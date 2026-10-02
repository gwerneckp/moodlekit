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


def test_cookies_reads_the_last_used_chromium_profile_not_the_first_one(monkeypatch, tmp_path):
    user_data = tmp_path / "Chrome"
    for profile in ("Default", "Profile 1", "Profile 24"):
        (user_data / profile).mkdir(parents=True)
        (user_data / profile / "Cookies").write_text("")
    (user_data / "Local State").write_text(
        '{"profile": {"last_used": "Profile 24", "last_active_profiles": ["Profile 24"]}}')

    monkeypatch.setattr("moodlekit.browser.sys.platform", "darwin")
    monkeypatch.setattr("moodlekit.browser.Browser.CHROMIUM_USER_DATA_DIRS",
                        {"chrome": (str(user_data), None, None)})

    seen = {}

    def fake_chrome(cookie_file=None, domain_name=""):
        seen["cookie_file"] = cookie_file
        return []

    monkeypatch.setattr("browser_cookie3.chrome", fake_chrome)

    Browser.cookies("chrome", "moodle.test")
    assert seen["cookie_file"] == str(user_data / "Profile 24" / "Cookies")


def test_cookies_falls_back_to_default_lookup_when_local_state_is_unreadable(monkeypatch):
    monkeypatch.setattr("moodlekit.browser.sys.platform", "darwin")
    monkeypatch.setattr("moodlekit.browser.Browser.CHROMIUM_USER_DATA_DIRS",
                        {"chrome": ("/nonexistent/path", None, None)})

    seen = {}

    def fake_chrome(cookie_file=None, domain_name=""):
        seen["cookie_file"] = cookie_file
        return []

    monkeypatch.setattr("browser_cookie3.chrome", fake_chrome)

    Browser.cookies("chrome", "moodle.test")
    assert seen["cookie_file"] is None
