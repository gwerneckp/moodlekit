# Contributing

Thanks for your interest! moodlekit is made for the **University of Bath's Moodle**, and that's the only site it's tested against. Contributions are welcome with that in mind.

## Using it at another university

Moodle sites differ a lot, so moodlekit may not work on yours out of the box. That's completely fine and expected. You can:

- **Fork it** and adapt it to your site. This is usually the quickest route. The site-specific parts are small: `Moodle._activities_from_html`, `Moodle.files` (folders and embedded files) and `Moodle.page` read HTML, so they're what differs between themes.
- **Open an issue** to say what worked and what didn't (site, login type, output of `moodle check`), with anything personal removed. It helps others at the same university.
- **Send a PR** if your change is general and doesn't change behaviour at Bath. I can only test against Bath, so I may not be able to accept changes I can't verify.

## Ground rules

- **Never commit real course material or real cookies**, not even in test fixtures. Write minimal synthetic HTML/JSON that reproduces the structure.
- Keep it simple: prefer extending the `Moodle` class over adding layers. New dependencies need a good reason (heavy ones go in an optional extra).
- Helpers go in a class: a private method on the class that uses them, or a staticmethod on `Utils` if shared. No loose module-level `_functions`.
- Prefer Moodle's AJAX web-service functions over scraping wherever one exists.

## Setup

```bash
uv sync --all-extras
uv run pytest
uv run ruff check src tests
```

Tests are offline: HTTP is mocked with [responses](https://github.com/getsentry/responses), and sync uses a fake client.
