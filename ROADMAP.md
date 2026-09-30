# Roadmap

moodlekit is built around the **University of Bath's Moodle**: new features are driven by what Bath students need, and tested there. Guiding rule: **stay small**. One `Moodle` class, plain dataclasses, and few dependencies. A feature earns its place if it's something students actually do on Moodle.

## Now (0.1): working at Bath

- [x] Log in from a browser session (Firefox, Chrome, Edge, Brave, Safari... via browser-cookie3) or a pasted cookie
- [x] Re-read the browser once when the session expires
- [x] Courses, course contents (incl. not-yet-released items), files, folders, page text, deadlines
- [x] Downloads that follow redirects to cloud storage and never overwrite
- [x] HTML lecture notes to one PDF (optional `[pdf]` extra)
- [x] `sync` with `moodle.toml`: layouts, excludes, dry run, `--mark-seen`, update detection, retry on failure
- [x] `moodle` CLI with `--json` everywhere
- [x] MCP server (optional `[mcp]` extra)
- [x] Offline test suite

## Next: more robust at Bath

- [ ] Recorded (anonymised) responses from Bath as test fixtures, so a Bath theme change is caught by tests
- [ ] **`moodle doctor`**: explain what's wrong (no cookie, expired, SSO redirect, Moodle too old, scraping selectors not matching)
- [ ] Gentle rate limiting and retry with backoff

## Nice to have: easier to adapt for other universities

Not a promise of support elsewhere, just making forks easier:

- [ ] An issue template for "what worked at my university" reports
- [ ] **API-token login** for sites that allow it (`Moodle(url, token=...)`), using the official REST API. `call()` already has the same shape, so this is just a second way of sending requests. It's more stable than the AJAX endpoint wherever tokens are available.
- [ ] **Auto-detect** the best login type from the site's public `tool_mobile_get_public_config`
- [ ] Test against the official [moodle-docker](https://github.com/moodlehq/moodle-docker) images (Moodle 3.11, 4.1 LTS, 4.5 LTS, 5.x) in CI

## Later: more of Moodle

- [ ] Assignment details: due date, submission status, feedback and grade (`mod_assign_*` where AJAX-enabled, else scraping)
- [ ] Grades overview
- [ ] Forum posts and announcements, as text ("what did the lecturer post this week?")
- [ ] Availability dates for unreleased items ("opens 5 Oct 12:15"), so sync can say *when*
- [ ] Book (`mod_book`) and Page (`mod_page`) to Markdown/PDF
- [ ] Panopto/lecture-recording links collected per week
- [ ] `sync` notifications (desktop notification, or a summary file an agent can read)

## Maybe / needs thought

- Store a pasted cookie in the system keychain (right now it's env-only, on purpose)
- Uploading/submitting coursework. High risk and needs care, so probably not.
- Other LMSs (Canvas, Blackboard). Out of scope for this package.

## Not planned

- Handling your password or automating SSO logins. Your browser does the logging in, and moodlekit only reuses the session.
- Bulk crawling of courses you aren't enrolled in.
