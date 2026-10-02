# Changelog

## 0.1.1 (unreleased)

- Fix: on multi-profile Chromium browsers, cookies could be read from the wrong profile,
  causing spurious "not logged in" prompts. Now reads the last-used profile instead.

## 0.1.0 (unreleased)

First version, built and tested at the University of Bath.

- `Moodle` client using a browser session (browser-cookie3) or a pasted cookie, with automatic re-read on expiry
- Defaults to the University of Bath's Moodle and your system's default browser; opens the browser to log in when needed
- Courses, course contents (including unreleased items), files, folders, page text, deadlines
- HTML-notes-to-PDF renderer (`[pdf]` extra)
- `moodle` CLI with `--json`
- MCP server (`[mcp]` extra, mcp>=2)
