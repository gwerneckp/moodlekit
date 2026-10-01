<p align="center">
  <img src="https://raw.githubusercontent.com/gwerneckp/moodlekit/main/assets/logo.svg" alt="moodlekit logo" width="128">
</p>

<h1 align="center">moodlekit</h1>

<p align="center"><b>Your Moodle, programmable.</b> Python API · CLI · AI agents, with the login you already have.</p>

<p align="center">
  <a href="https://github.com/gwerneckp/moodlekit/blob/main/assets/demo.mp4">
    <img src="https://raw.githubusercontent.com/gwerneckp/moodlekit/main/assets/demo.gif" alt="moodlekit demo: listing courses, seeing unreleased items, reading pages, HTML notes to PDF, the Python API, and asking an agent what's new." width="800">
  </a>
  <br>
  <sub>▶️ <a href="https://github.com/gwerneckp/moodlekit/blob/main/assets/demo.mp4">Watch the video</a></sub>
</p>

Use Moodle from Python, the command line, or an AI agent, **with the login you already have in your browser**. No API token needed, so it works even where the university uses single sign-on (Microsoft, Google, SAML) and has disabled Moodle's mobile/web-service token.

```console
$ moodle courses
  61802  MA22038                MA22038: Probabilistic modelling / Probability 2
  ...
$ moodle ls MA22038
## Problem Sheets
  resource  Problem Sheet 1 (pdf)
  resource  Sheet 1 solutions to remaining questions (pdf)  [not available yet]
```

> [!NOTE]
> **Made for the University of Bath.**
> I built moodlekit for my own studies at the [University of Bath](https://moodle.bath.ac.uk) (Moodle 4.5, Microsoft login). Bath is where it's tested, and Bath is what it's designed around.
>
> Every Moodle is different: each university has its own version, theme, plugins and login setup, and moodlekit relies partly on reading HTML pages. So it may well work at your university, partly work, or not work at all, and it can break at Bath too when the site changes. That's expected, not a bug in your setup.
>
> **Using another Moodle?** You're very welcome to try it. If something doesn't work, the best route is to **fork it** and adapt it to your site. The code is small and the site-specific parts are easy to find (see [How it works](#how-it-works)). You can also **open an issue** saying what you found, or send a PR if your change doesn't affect Bath. Just know I can only test changes against Bath.

| Site | Moodle | Login | Status |
|---|---|---|---|
| University of Bath | 4.5 | Microsoft SSO | ✅ Tested: courses, contents, files, folders, pages, HTML notes to PDF, CLI, MCP (Firefox and Chrome) |
| *yours?* | | | [open an issue](https://github.com/gwerneckp/moodlekit/issues) or fork |

## What it can do

- **List your courses** and **everything on a course page** (files, folders, assignments, forums, pages...), including items that are **listed but not released yet**.
- **Download** files and folders, and **turn HTML lecture notes into one PDF**.
- **Read pages** as plain text (assignment briefs, forum posts, course diaries).
- **Upcoming deadlines** across your courses.
- Everything is available as a **Python library**, a **`moodle` command** (with `--json` for scripts and agents), and an optional **MCP server**.

## Install

```bash
pip install pymoodlekit                      # library + `moodle` command
pip install "pymoodlekit[pdf]"               # + HTML-notes-to-PDF (then: playwright install chromium)
pip install "pymoodlekit[mcp]"               # + MCP server for AI agents
```

Requires Python 3.11+.

## Logging in

moodlekit doesn't handle your password or your SSO login. You log in to Moodle normally in your browser, and moodlekit reads that browser's session cookie (using [browser-cookie3](https://github.com/borisbabic/browser_cookie3)).

```bash
moodle check          # "Logged in to https://moodle.bath.ac.uk with firefox, 15 courses visible."
```

That's it. By default moodlekit uses **the University of Bath's Moodle** and **your system's default browser** (if it's one of the supported ones below, otherwise Firefox). If you're not logged in, it **opens Moodle in that browser**, waits while you log in, and then carries on with your command.

The cookie is read fresh every time and **never written to disk** by moodlekit. When the session expires, moodlekit re-reads the browser first, so staying logged in there keeps it working.

To change the defaults (flags win over environment variables):

| | flag | environment | default |
|---|---|---|---|
| site | `--url moodle.example.ac.uk` | `MOODLE_URL` | `https://moodle.bath.ac.uk` |
| browser | `--browser chrome` | `MOODLE_BROWSER` | your default browser |
| raw cookie instead | `--cookie` | `MOODLE_COOKIE` | none |

Supported browsers: Firefox, Chrome, Safari, Edge, Brave, Arc, Chromium, Opera, Vivaldi, LibreWolf.

**Firefox tip:** Firefox is the most reliable choice on macOS. Chrome-based browsers encrypt cookies with a key in the system keychain, so you may get a keychain prompt.

**Manual cookie:** open your Moodle in any browser, then DevTools → Application/Storage → Cookies. Copy the `MoodleSession…` cookie and `export MOODLE_COOKIE='MoodleSessionXYZ=abc123'` (or just the value).

## Command line

```bash
moodle check                              # is the login working?
moodle courses [inprogress|past|future|all]
moodle ls MA22038                         # sections + activities (id, shortname or part of the name)
moodle files <activity-url>               # files behind a resource/folder/page
moodle get <url> -o notes/                # download them (never overwrites: "x (1).pdf")
moodle get <url> --pdf notes.pdf          # HTML notes -> one PDF   (needs [pdf])
moodle read <url>                         # page text + file links
moodle deadlines --days 14
moodle mcp                                # MCP server               (needs [mcp])
```

Add `--json` before the command for machine-readable output, e.g. `moodle --json ls MA22038`.

## Python

```python
from moodlekit import Moodle

m = Moodle()                                   # Bath + your default browser
# m = Moodle("moodle.example.ac.uk", browser="chrome")
m.login()                                      # optional: opens the browser if you're not logged in

for course in m.courses():
    print(course.id, course.shortname, course.name)

for act in m.activities("MA22038"):            # id, shortname, or part of the name
    if act.type == "resource" and act.available:
        m.download(act, "downloads/")          # -> [Path(...)]

m.page("https://moodle.bath.ac.uk/mod/page/view.php?id=123").text
m.deadlines(days=14)

# Escape hatches for anything not wrapped yet:
m.call("core_course_get_enrolled_courses_by_timeline_classification", classification="all",
       offset=0, limit=0, sort="fullname")     # any AJAX-enabled web service function
m.get("/course/view.php?id=61802").text        # any page, with your session
```

Results are plain dataclasses (`Course`, `Activity`, `File`, `Event`, `Page`). `Utils.to_dict(result)` turns any of them into JSON-ready data. Errors are `MoodleError`, and `NotLoggedIn` when the session is missing or expired.

HTML to PDF: `PdfRenderer(m).render(activity_or_url, "notes.pdf")`.

## MCP server (AI agents)

```bash
pip install "pymoodlekit[mcp]"
claude mcp add moodle -- moodle mcp
```

Tools: `list_courses`, `list_activities`, `list_files`, `read_page`, `download`, `upcoming_deadlines`. If you're not logged in, the first tool call opens Moodle in your browser and waits for you.

Agents can also just use the CLI with `--json`, which is often simpler.

## How it works

Moodle's official web-service API needs a per-user token. Many SSO universities don't let students create one, and disable the mobile-app login that would hand one out. But Moodle's own web pages talk to an internal AJAX endpoint (`/lib/ajax/service.php`), authenticated by the normal session cookie and a `sesskey` embedded in every page. moodlekit does the same:

| Feature | How | Fragility |
|---|---|---|
| Courses, deadlines | AJAX web-service functions | Low: stable Moodle APIs |
| Course contents | AJAX `core_courseformat_get_state` (Moodle 4.0+), HTML fallback for older sites | Low / **high for the fallback** |
| Files | Follows resource redirects to `pluginfile.php` (and on to cloud storage such as S3) | Medium |
| Folders, embedded files, page text | **HTML scraping** (`#region-main`) | **High**: theme-dependent |
| HTML notes to PDF | Headless Chromium with your session | Medium |

Only AJAX-enabled functions can be called this way, which is why some features need scraping. See [ROADMAP.md](https://github.com/gwerneckp/moodlekit/blob/main/ROADMAP.md) for what's next.

## Security and fair use

- **A Moodle session cookie is full access to your account.** moodlekit only sends it to your Moodle site, never logs or stores it, and has no telemetry. Don't paste your cookie into issues or chats.
- **Course material is your university's copyright.** Download it for your own study, and don't redistribute it (including by committing it to a public repo).
- **Be polite to your university's servers.** moodlekit makes about one request per item, so don't loop it every minute. Check your university's IT acceptable-use policy.
- This is an unofficial project, not affiliated with Moodle HQ or any university.

## Development

```bash
uv sync --all-extras
uv run pytest            # offline tests with mocked HTTP; no real Moodle needed
uv run ruff check src tests
```

See [CONTRIBUTING.md](https://github.com/gwerneckp/moodlekit/blob/main/CONTRIBUTING.md).

## License

[MIT](https://github.com/gwerneckp/moodlekit/blob/main/LICENSE)
