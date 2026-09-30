"""Sync tests with a fake Moodle (no network)."""

import json

from moodlekit import Activity, Course, File, Sync

STATE_NAME = Sync.STATE_NAME


def sync(moodle, config, **kwargs):
    return Sync(moodle, config).run(**kwargs)


class FakeMoodle:
    def __init__(self):
        self.acts = [
            Activity(1, "Sheet 1 (pdf)", "resource", "u1", "Problem Sheets", 1, True, 5),
            Activity(2, "Sheet 1 (html)", "resource", "u2", "Problem Sheets", 1, True, 5),
            Activity(3, "Solutions", "resource", "u3", "Problem Sheets", 1, False, 5),
            Activity(4, "Coursework", "assign", "u4", "Assessment", 2, True, 5),
            Activity(5, "Notes", "resource", "u5", "Notes", 3, True, 5),
        ]
        self.files_by_url = {
            "u1": [File("sheet1.pdf", "https://m/pluginfile.php/1/content/1/sheet1.pdf")],
            "u2": [File("sheet1.html", "https://m/pluginfile.php/2/content/1/sheet1.html")],
            "u5": [File("index.html", "https://m/pluginfile.php/5/content/1/index.html")],
        }
        self.saved = []

    def course(self, key):
        return Course(5, "MA1", "Maths", "")

    def activities(self, course):
        return self.acts

    def files(self, act):
        return self.files_by_url.get(act.url, [])

    def save(self, f, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f.url)
        self.saved.append(path)
        return path


def write_config(tmp_path, extra=""):
    cfg = tmp_path / "moodle.toml"
    cfg.write_text('url = "https://m"\nexclude = ["*(html)*"]\n'
                   f'[courses.MA1]\npath = "Maths"\n{extra}')
    return cfg


def kinds(report):
    return sorted((c.kind, c.activity) for c in report.changes)


def test_first_sync_downloads_and_reports(tmp_path):
    m, cfg = FakeMoodle(), write_config(tmp_path)
    report = sync(m, cfg)
    assert kinds(report) == [("downloaded", "Sheet 1 (pdf)"), ("new-activity", "Coursework"),
                             ("skipped", "Notes"), ("upcoming", "Solutions")]
    assert (tmp_path / "Maths/Problem Sheets/sheet1.pdf").exists()
    assert (tmp_path / STATE_NAME).exists()


def test_second_sync_is_quiet_even_if_files_moved(tmp_path):
    m, cfg = FakeMoodle(), write_config(tmp_path)
    sync(m, cfg)
    (tmp_path / "Maths/Problem Sheets/sheet1.pdf").rename(tmp_path / "moved.pdf")
    report = sync(m, cfg)
    assert kinds(report) == [("skipped", "Notes"), ("upcoming", "Solutions")]
    assert len(m.saved) == 1


def test_reuploaded_file_is_reported_as_updated(tmp_path):
    m, cfg = FakeMoodle(), write_config(tmp_path)
    sync(m, cfg)
    m.files_by_url["u1"] = [File("sheet1.pdf", "https://m/pluginfile.php/1/content/2/sheet1.pdf")]
    report = sync(m, cfg)
    [change] = report.of("updated")
    assert change.path == "Maths/Problem Sheets/sheet1 (1).pdf"  # old copy kept


def test_dry_run_changes_nothing(tmp_path):
    m, cfg = FakeMoodle(), write_config(tmp_path)
    report = sync(m, cfg, dry_run=True)
    assert report.of("downloaded") and not m.saved
    assert not (tmp_path / STATE_NAME).exists()


def test_mark_seen_records_without_downloading(tmp_path):
    m, cfg = FakeMoodle(), write_config(tmp_path)
    sync(m, cfg, mark_seen=True)
    assert not m.saved
    assert not sync(m, cfg).of("downloaded")


def test_layout_and_per_course_exclude(tmp_path):
    m = FakeMoodle()
    cfg = write_config(tmp_path, 'layout = "{filename}"\nexclude = ["coursework"]\n')
    report = sync(m, cfg)
    assert (tmp_path / "Maths/sheet1.pdf").exists()
    assert not report.of("new-activity")


def test_state_file_is_json_with_paths(tmp_path):
    m, cfg = FakeMoodle(), write_config(tmp_path)
    sync(m, cfg)
    state = json.loads((tmp_path / STATE_NAME).read_text())
    [entry] = state["files"].values()
    assert entry["path"] == "Maths/Problem Sheets/sheet1.pdf" and entry["activity"] == 1


def test_a_failing_file_is_reported_and_retried(tmp_path):
    m, cfg = FakeMoodle(), write_config(tmp_path)
    real_save = m.save
    m.save = lambda f, path: (_ for _ in ()).throw(OSError("disk full"))
    report = sync(m, cfg)
    [failed] = report.of("failed")
    assert failed.note == "disk full"
    m.save = real_save
    assert sync(m, cfg).of("downloaded")  # not recorded, so it's retried
