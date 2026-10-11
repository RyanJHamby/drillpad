import pytest
from fastapi.testclient import TestClient

from drillpad.web.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "curriculum.yaml").write_text('id: badge-pack\ntitle: "Badge"\nlevels:\n  - id: l\n    title: L\n    units:\n      - module: m\n')
    mod = pack / "modules" / "m"
    (mod / "lessons").mkdir(parents=True)
    (mod / "module.yaml").write_text('title: "M"\nlanguage: systems\ndescription: "d"\nlessons:\n'
                                     '- id: 01-checked\n  title: "Checked"\n  practice: []\n'
                                     '- id: 02-draft\n  title: "Draft"\n  practice: []\n'
                                     '- id: 03-planned\n  title: "Planned"\n  practice: []\n')
    (mod / "lessons" / "01-checked.md").write_text("# Checked\n\nLast verified: 2026-03-04\n\nbody\n")
    (mod / "lessons" / "02-draft.md").write_text('# Draft\n\nDrafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking)\n\nbody\n')
    monkeypatch.setenv("DRILLPAD_CURRICULA_PATH", str(pack))
    return TestClient(create_app(tmp_path / "t.db"))


def test_lessons_report_their_verification_date_or_none(client):
    mod = next(m for m in client.get("/api/modules").json() if m["id"] == "badge-pack.m")
    by = {ls["id"]: ls for ls in mod["lessons"]}
    assert by["01-checked"]["verified"] == "2026-03-04"
    assert by["02-draft"]["verified"] is None, "a 'Drafted ... (not yet verified)' line must not count as verification"
    assert by["03-planned"]["written"] is False and by["03-planned"]["verified"] is None
    assert client.get("/api/modules/badge-pack.m/01-checked").json()["verified"] == "2026-03-04"
    assert client.get("/api/modules/badge-pack.m/02-draft").json()["verified"] is None


def test_the_shipped_course_is_honest_about_review_status(client):
    mods = client.get("/api/modules").json()
    core = [ls for m in mods if "core" in m["curriculum_ids"] for ls in m["lessons"] if ls["written"]]
    assert core and all(ls["verified"] in (None,) or len(ls["verified"]) == 10 for ls in core)
