# Changelog

## 0.1.0 (unreleased)

First version, built and tested at the University of Bath.

- `Moodle` client using a browser session (browser-cookie3) or a pasted cookie, with automatic re-read on expiry
- Courses, course contents (including unreleased items), files, folders, page text, deadlines
- HTML-notes-to-PDF renderer (`[pdf]` extra)
- `Sync` with `moodle.toml`, `.moodle-state.json`, dry run, `--mark-seen`, update detection
- `moodle` CLI with `--json`
- MCP server (`[mcp]` extra, mcp>=2)
