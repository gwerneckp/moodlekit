# moodlekit

Use Moodle from Python, the command line, or an AI agent, **with the login you already have in your browser**. No API token needed, so it works even where the university uses single sign-on (Microsoft, Google, SAML) and has disabled Moodle's mobile/web-service token.

```console
$ moodle courses
  61802  MA22038                MA22038: Probabilistic modelling / Probability 2
  ...
$ moodle sync
Downloaded:
  [MA22038] Problem Sheet 1 (pdf)  ->  Probabilistic_Modelling_MA22038/Problem Sheets/MA22038-sheet1-2026.pdf
Listed, not released yet:
  [MA22038] Sheet 1 solutions to remaining questions (pdf)
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
| University of Bath | 4.5 | Microsoft SSO | ✅ Tested: courses, contents, files, folders, pages, HTML notes to PDF, sync, CLI, MCP (Firefox and Chrome) |
| *yours?* | | | [open an issue](../../issues) or fork |

## What it can do

- **List your courses** and **everything on a course page** (files, folders, assignments, forums, pages...), including items that are **listed but not released yet**.
- **Download** files and folders, and **turn HTML lecture notes into one PDF**.
- **Read pages** as plain text (assignment briefs, forum posts, course diaries).
- **Upcoming deadlines** across your courses.
- **`sync`**: mirror chosen courses into your own folders and tell you what's new. Files you move or rename are not downloaded again, and a file the lecturer re-uploads shows up as *updated*.
- Everything is available as a **Python library**, a **`moodle` command** (with `--json` for scripts and agents), and an optional **MCP server**.

## Install

```bash
pip install moodlekit                      # library + `moodle` command
pip install "moodlekit[pdf]"               # + HTML-notes-to-PDF (then: playwright install chromium)
pip install "moodlekit[mcp]"               # + MCP server for AI agents
```

Until it's on PyPI, install from a clone: `pip install -e ".[pdf,mcp]"`, or `uv sync --all-extras`.

Requires Python 3.11+.

## Logging in

moodlekit doesn't handle your password or your SSO login. You log in to Moodle normally in your browser, and moodlekit reads that browser's session cookie (using [browser-cookie3](https://github.com/borisbabic/browser_cookie3)).

1. Log in to your Moodle in **Firefox** (the default), or Chrome, Edge, Brave, Safari...
2. Tell moodlekit your site:
   ```bash
   export MOODLE_URL=https://moodle.bath.ac.uk
   moodle check          # "Logged in to https://moodle.bath.ac.uk, 15 courses visible."
   ```

The cookie is read fresh every time and **never written to disk** by moodlekit. When the session expires, moodlekit re-reads the browser once, so staying logged in in your browser keeps it working.

Options, from highest priority to lowest:

| | flag | environment | `moodle.toml` |
|---|---|---|---|
| site | `--url` | `MOODLE_URL` | `url = "..."` |
| browser | `--browser chrome` | `MOODLE_BROWSER` | `browser = "chrome"` |
| raw cookie instead | `--cookie` | `MOODLE_COOKIE` | (not supported, keep secrets out of files) |

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
moodle sync [-n] [--mark-seen] [COURSE…]  # see below
moodle mcp                                # MCP server               (needs [mcp])
```

Add `--json` before the command for machine-readable output, e.g. `moodle --json ls MA22038`.

## Python

```python
from moodlekit import Moodle

m = Moodle("https://moodle.bath.ac.uk", browser="firefox")

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

## Sync

Put a `moodle.toml` at the root of your notes folder:

```toml
url = "https://moodle.bath.ac.uk"
browser = "firefox"
exclude = ["*(html)*"]            # skip activities whose name matches (case-insensitive globs)
layout = "{section}/{filename}"   # {course} {section} {activity} {filename}
render_html = true                # HTML material -> PDF (needs [pdf])

[courses.MA22038]                 # shortname, id, or part of the course name
path = "Year_2/Semester_1/Probabilistic_Modelling_MA22038"

[courses.MA22014]
path = "Year_2/Semester_1/Statistics_2A_MA22014"
layout = "{filename}"             # per-course overrides: layout, exclude
```

```bash
moodle sync -n            # dry run: "has anything been published?"
moodle sync               # download what's new
moodle sync MA22038       # just one course
moodle sync --mark-seen   # adopting a folder you already filled by hand: record everything
                          # as downloaded, without downloading
```

What it reports:

- **Downloaded / Would download**: new files.
- **Updated on Moodle**: a file you already had was re-uploaded. The new copy is saved next to the old one.
- **New activities**: new assignments, forums, links, quizzes... (reported once, not downloaded).
- **Listed, not released yet**: things like solutions that open on a date.
- **Skipped**: HTML content when `render_html` is off.
- **Failed**: will be retried on the next sync.

It keeps a `.moodle-state.json` next to `moodle.toml`. It's keyed by file URL, and Moodle puts a revision number in that URL, so you can reorganise downloaded files however you like. Commit the state file if you want sync history shared across machines; add it to `.gitignore` otherwise.

Pair it with cron/launchd, or an agent, for a weekly "what's new on Moodle" check.

## MCP server (AI agents)

```bash
pip install "moodlekit[mcp]"
claude mcp add moodle -e MOODLE_URL=https://moodle.bath.ac.uk -- moodle mcp
```

Tools: `list_courses`, `list_activities`, `list_files`, `read_page`, `download`, `upcoming_deadlines`, `whats_new` (a sync dry run, if a `moodle.toml` is found from the server's working directory).

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

Only AJAX-enabled functions can be called this way, which is why some features need scraping. See [ROADMAP.md](ROADMAP.md) for what's next.

## Security and fair use

- **A Moodle session cookie is full access to your account.** moodlekit only sends it to your Moodle site, never logs or stores it, and has no telemetry. Don't paste your cookie into issues or chats.
- **Course material is your university's copyright.** Download it for your own study, and don't redistribute it (including by committing it to a public repo).
- **Be polite to your university's servers.** moodlekit makes about one request per item. Don't run sync every minute. Check your university's IT acceptable-use policy.
- This is an unofficial project, not affiliated with Moodle HQ or any university.

## Development

```bash
uv sync --all-extras
uv run pytest            # offline tests with mocked HTTP; no real Moodle needed
uv run ruff check src tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
