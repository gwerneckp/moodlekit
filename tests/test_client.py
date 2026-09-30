"""Client tests against mocked HTTP responses (synthetic data, no real Moodle needed)."""

import json

import pytest
import responses

from moodlekit import Activity, Browser, Moodle, MoodleError, NotLoggedIn

URL = "https://moodle.test"
AJAX = f"{URL}/lib/ajax/service.php"


@pytest.fixture
def m():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.get(f"{URL}/my/", body='<script>M.cfg = {"sesskey":"abc123"};</script>')
        client = Moodle(URL, cookie="MoodleSessiontest=xyz")
        client.rsps = rsps
        yield client


def ajax_ok(data):
    return json.dumps([{"error": False, "data": data}])


def test_defaults_to_bath_and_default_browser(monkeypatch):
    monkeypatch.setattr(Browser, "default", classmethod(lambda cls: "chrome"))
    monkeypatch.setattr(Browser, "cookies", lambda name, host: {})
    m = Moodle()
    assert m.url == "https://moodle.bath.ac.uk" and m.host == "moodle.bath.ac.uk"
    assert m.browser == "chrome"


def test_url_without_scheme(monkeypatch):
    monkeypatch.setattr(Browser, "cookies", lambda name, host: {})
    m = Moodle("moodle.example.ac.uk/", browser="Firefox")
    assert (m.url, m.host, m.browser) == ("https://moodle.example.ac.uk", "moodle.example.ac.uk",
                                          "firefox")


def test_not_logged_in_yet_is_fine_until_used():
    with responses.RequestsMock() as rsps:
        rsps.get(f"{URL}/my/", status=303, headers={"Location": f"{URL}/login/index.php"})
        rsps.get(f"{URL}/login/index.php", body="<form>login</form>")
        m = Moodle(URL, cookie="other=1")  # no MoodleSession cookie: no error yet
        with pytest.raises(NotLoggedIn):
            m.courses()


def test_login_opens_browser_and_waits(monkeypatch):
    opened, loads = [], []

    def fake_cookies(name, host):
        loads.append(name)
        return {} if len(loads) < 3 else {"MoodleSessiontest": "fresh"}

    monkeypatch.setattr(Browser, "cookies", fake_cookies)
    monkeypatch.setattr(Browser, "open", lambda name, url: opened.append((name, url)))
    monkeypatch.setattr("moodlekit.client.time.sleep", lambda s: None)
    with responses.RequestsMock() as rsps:
        rsps.get(f"{URL}/my/", body='"sesskey":"k1"')
        m = Moodle(URL, browser="firefox")
        m.login(wait=60)
        assert m.sesskey == "k1"
    assert opened == [("firefox", f"{URL}/my/")]


def test_courses_unescapes_names(m):
    m.rsps.post(AJAX, body=ajax_ok({"courses": [
        {"id": 7, "shortname": "MA101", "fullname": "Algebra &amp; Geometry ",
         "viewurl": f"{URL}/course/view.php?id=7"}]}))
    [c] = m.courses()
    assert (c.id, c.shortname, c.name) == (7, "MA101", "Algebra & Geometry")
    sent = json.loads(m.rsps.calls[-1].request.body)
    assert sent[0]["methodname"] == "core_course_get_enrolled_courses_by_timeline_classification"
    assert "sesskey=abc123" in m.rsps.calls[-1].request.url


def test_course_lookup(m):
    m.rsps.post(AJAX, body=ajax_ok({"courses": [
        {"id": 1, "shortname": "MA101", "fullname": "Algebra", "viewurl": ""},
        {"id": 2, "shortname": "MA102", "fullname": "Analysis", "viewurl": ""}]}))
    assert m.course("ma102").id == 2
    assert m.course("1").id == 1
    assert m.course("analy").id == 2
    with pytest.raises(MoodleError, match="several"):
        m.course("MA10")


STATE = {
    "course": {"id": "5"},
    "section": [
        {"number": 1, "title": "Sheets", "cmlist": ["12", "13", "14"]},
        {"number": 0, "title": "Intro &amp; admin", "cmlist": ["11"]},
    ],
    "cm": [
        {"id": "11", "name": "Forum", "module": "forum", "uservisible": True,
         "url": f"{URL}/mod/forum/view.php?id=11"},
        {"id": "12", "name": "Week 1", "module": "label", "uservisible": True},
        {"id": "13", "name": "Sheet 1 (pdf)", "module": "resource", "uservisible": True,
         "url": f"{URL}/mod/resource/view.php?id=13"},
        {"id": "14", "name": "Solutions", "module": "resource", "uservisible": False,
         "url": f"{URL}/mod/resource/view.php?id=14"},
    ],
}


def test_activities_from_course_state(m):
    m.rsps.post(AJAX, body=ajax_ok(json.dumps(STATE)))
    acts = m.activities(m_course())
    assert [a.id for a in acts] == [11, 13, 14]  # section order, label skipped
    assert acts[0].section == "Intro & admin"
    assert acts[2].available is False


def m_course():
    from moodlekit import Course
    return Course(5, "C5", "Course five", "")


def test_activities_fall_back_to_html(m):
    m.rsps.post(AJAX, body=json.dumps([{"error": True, "exception": {
        "errorcode": "invalidrecord", "message": "no such function"}}]))
    m.rsps.get(f"{URL}/course/view.php", body="""
      <li class="section"><h3 class="sectionname">Week 1</h3>
        <a href="/mod/resource/view.php?id=9"><span class="instancename">Notes
          <span class="accesshide">File</span></span></a></li>""")
    [a] = m.activities(m_course())
    assert (a.id, a.name, a.type, a.section) == (9, "Notes", "resource", "Week 1")


def test_files_follows_resource_redirect(m):
    pf = f"{URL}/pluginfile.php/1/mod_resource/content/3/Sheet%201.pdf"
    m.rsps.get(f"{URL}/mod/resource/view.php", status=303, headers={"Location": pf})
    [f] = m.files(Activity(13, "Sheet", "resource", f"{URL}/mod/resource/view.php?id=13",
                           "", 0, True, 5))
    assert (f.name, f.url) == ("Sheet 1.pdf", pf)


def test_files_from_embedded_page(m):
    m.rsps.get(f"{URL}/mod/folder/view.php", body="""<div id="region-main">
      <a href="/pluginfile.php/2/mod_folder/content/0/a.pdf?forcedownload=1">a.pdf</a>
      <a href="/pluginfile.php/2/mod_folder/content/0/a.pdf?forcedownload=1">again</a>
      <object data="/pluginfile.php/2/mod_folder/content/0/b.pdf"></object></div>""")
    files = m.files(f"{URL}/mod/folder/view.php?id=4")
    assert [f.name for f in files] == ["a.pdf", "b.pdf"]


def test_save_follows_redirect_to_storage(m, tmp_path):
    pf = f"{URL}/pluginfile.php/1/x.pdf"
    m.rsps.get(pf, status=303, headers={"Location": "https://storage.test/blob?sig=1"})
    m.rsps.get("https://storage.test/blob", body=b"%PDF-1.7")
    path = m.save(pf, tmp_path / "sub" / "x.pdf")
    assert path.read_bytes() == b"%PDF-1.7"


def test_download_never_overwrites(m, tmp_path):
    pf = f"{URL}/pluginfile.php/1/x.pdf"
    m.rsps.get(pf, body=b"new")
    (tmp_path / "x.pdf").write_bytes(b"old")
    [path] = m.download(pf, tmp_path)
    assert path.name == "x (1).pdf" and (tmp_path / "x.pdf").read_bytes() == b"old"


def test_login_redirect_raises_not_logged_in(m):
    m.rsps.get(f"{URL}/mod/page/view.php", status=303,
               headers={"Location": f"{URL}/login/index.php"})
    m.rsps.get(f"{URL}/login/index.php", body="<form>login</form>")
    with pytest.raises(NotLoggedIn):
        m.page(f"{URL}/mod/page/view.php?id=1")


def test_ajax_login_error_raises_not_logged_in(m):
    m.rsps.post(AJAX, body=json.dumps([{"error": True, "exception": {
        "errorcode": "servicerequireslogin", "message": "expired"}}]))
    with pytest.raises(NotLoggedIn):
        m.courses()


def test_browser_session_is_reloaded_once_on_expiry(monkeypatch):
    loads = []

    def fake_cookies(name, host):
        loads.append(name)
        return {"MoodleSessiontest": f"v{len(loads)}"}

    monkeypatch.setattr(Browser, "cookies", fake_cookies)
    with responses.RequestsMock() as rsps:
        rsps.get(f"{URL}/my/", body='"sesskey":"k1"')
        rsps.post(AJAX, body=json.dumps([{"error": True, "exception": {
            "errorcode": "servicerequireslogin"}}]))
        rsps.post(AJAX, body=ajax_ok({"courses": []}))
        m = Moodle(URL, browser="firefox")
        assert m.courses() == []
    assert len(loads) == 2


def test_page_text_and_links(m):
    m.rsps.get(f"{URL}/mod/assign/view.php", body="""<title>Coursework 1</title>
      <nav>menu</nav><div id="region-main"><h2>Brief</h2><p>Do the thing.</p>
      <a href="/pluginfile.php/3/brief.pdf">brief.pdf</a><a href="/user/1">me</a></div>""")
    page = m.page(f"{URL}/mod/assign/view.php?id=3")
    assert page.title == "Coursework 1"
    assert "Do the thing." in page.text and "menu" not in page.text
    assert page.links == [{"text": "brief.pdf", "url": f"{URL}/pluginfile.php/3/brief.pdf"}]
