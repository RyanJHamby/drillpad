import pytest
from fastapi.testclient import TestClient

from drillpad.core import curricula as cur
from drillpad.web.app import create_app


def write_curriculum(root, cid, units="", extra="", title="Demo Track", folder=None):
    d = root / (folder or cid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "curriculum.yaml").write_text(
        f'id: {cid}\ntitle: "{title}"\nsummary: A demo.\nlevel: beginner\nstatus: draft\n{extra}'
        f"levels:\n  - id: first\n    title: First\n    units:\n{units}")
    return d


def write_module(curriculum_dir, key, lesson="# Hello\nbody\n"):
    m = curriculum_dir / "modules" / key
    (m / "lessons").mkdir(parents=True)
    (m / "module.yaml").write_text(f'title: "Module {key}"\nlanguage: systems\ndescription: "d"\nlessons:\n- id: 01-intro\n  title: "Intro"\n  practice: []\n')
    (m / "lessons" / "01-intro.md").write_text(lesson)


UNITS = ("      - module: ready-one\n      - module: later-one\n        title: Later One\n        summary: Planned.\n"
         "      - uses: reasoning-under-constraints\n      - uses: no-such-module\n")


def test_unit_status_namespacing_and_problems(tmp_path):
    d = write_curriculum(tmp_path, "demo-track", UNITS)
    write_module(d, "ready-one")
    c, probs = cur.read_curriculum(d, "bundled")
    assert probs == [] and c.id == "demo-track"
    by = {u.key: u for u in c.units()}
    assert by["ready-one"].module_id == "demo-track.ready-one" and by["ready-one"].status == "ready"
    assert by["ready-one"].title == "Module ready-one", "title comes from module.yaml when the module exists"
    assert by["later-one"].status == "planned" and by["later-one"].title == "Later One"
    assert cur.owned_modules(c) == {"demo-track.ready-one": d / "modules" / "ready-one"}


@pytest.mark.parametrize("units,needle", [
    ("      - title: nothing\n", "exactly one of"),
    ("      - module: x\n        uses: y\n", "exactly one of"),
    ("      - module: BadKey\n        title: t\n", "bad module key"),
    ("      - module: planned-no-title\n", "needs a title"),
    ("      - module: a\n        title: A\n      - module: a\n        title: A again\n", "appears twice"),
])
def test_validation_problems(tmp_path, units, needle):
    d = write_curriculum(tmp_path, "demo-track", units)
    _c, probs = cur.read_curriculum(d, "bundled")
    assert any(needle in p for p in probs), probs


def test_invalid_ids_and_folder_name_rules(tmp_path):
    assert cur.read_curriculum(write_curriculum(tmp_path, "Bad_Id"), "bundled")[0] is None
    assert cur.read_curriculum(write_curriculum(tmp_path, "core"), "bundled")[0] is None, "'core' is reserved"
    c, probs = cur.read_curriculum(write_curriculum(tmp_path, "right-id", folder="wrong-folder"), "bundled")
    assert c is not None and any("folder name" in p for p in probs)
    c, probs = cur.read_curriculum(write_curriculum(tmp_path, "right-id", folder="any-clone-name"), "external")
    assert probs == [], "an external pack may live in any folder name"


def test_reuse_resolution_and_duplicate_ids(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    write_curriculum(a, "same-id", "      - uses: known-module\n      - uses: gone-module\n")
    write_curriculum(b, "same-id", "      - uses: known-module\n")
    monkeypatch.setattr(cur, "roots", lambda: [("bundled", a), ("external", b)])
    found, probs = cur.load_curricula({"known-module"})
    assert [u.status for u in found["same-id"].units()] == ["ready", "missing"]
    assert any("duplicate curriculum id" in p for p in probs) and any("gone-module" in p for p in probs)


def test_curriculum_dirs_accepts_a_root_that_is_itself_a_curriculum(tmp_path):
    d = write_curriculum(tmp_path, "solo-pack", "      - module: x\n        title: X\n")
    assert cur.curriculum_dirs(d) == [d] and cur.curriculum_dirs(tmp_path) == [d]


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "t.db"))


def test_core_is_the_default_curriculum_and_matches_the_stage_list(client):
    cs = {c["id"]: c for c in client.get("/api/curricula").json()}
    assert next(iter(cs)) == "core"
    mods = client.get("/api/modules").json()
    core_ids = {u["module_id"] for lv in cs["core"]["levels"] for u in lv["units"]}
    assert core_ids == {m["id"] for m in mods if "core" in m["curriculum_ids"]}
    assert cs["core"]["levels"][0]["id"] == "0-thinking-tools" and cs["core"]["progress"]["lessons"] > 100


def test_shipped_curricula_are_valid_and_reuse_real_modules(client):
    found, probs = cur.load_curricula({m["id"] for m in client.get("/api/modules").json() if not m.get("curriculum_id")})
    shipped = {c.id: c for c in found.values() if c.source == "bundled"}
    assert {"trading-hft", "power-grid-compute"} <= set(shipped)
    assert [p for p in probs if any(p.startswith(i + ":") for i in shipped)] == []
    cs = {c["id"]: c for c in client.get("/api/curricula").json()}
    for cid in ("trading-hft", "power-grid-compute"):
        assert cs[cid]["progress"]["ready_units"] > 0 and cs[cid]["progress"]["planned_units"] > 0
        assert not any(u["status"] == "missing" for lv in cs[cid]["levels"] for u in lv["units"])


def test_external_curriculum_plugs_in_with_namespaced_progress_and_whiteboard(tmp_path, monkeypatch):
    pack = tmp_path / "my-pack-clone"
    d = write_curriculum(pack, "my-pack", "      - module: basics\n      - module: next-up\n        title: Next Up\n      - uses: reasoning-under-constraints\n", folder=".")
    write_module(d, "basics")
    monkeypatch.setenv("DRILLPAD_CURRICULA_PATH", str(pack))
    c = TestClient(create_app(tmp_path / "t.db"))
    cs = {x["id"]: x for x in c.get("/api/curricula").json()}
    mods = {m["id"]: m for m in c.get("/api/modules").json()}
    reused = len(mods["reasoning-under-constraints"]["lessons"])
    assert cs["my-pack"]["source"] == "external"
    assert cs["my-pack"]["progress"] == {"lessons": 1 + reused, "done": 0, "ready_units": 2, "planned_units": 1}, "reused modules count"
    gid = "my-pack.basics"
    assert mods[gid]["curriculum_id"] == "my-pack" and mods[gid]["curriculum_ids"] == ["my-pack"]
    assert "my-pack" in mods["reasoning-under-constraints"]["curriculum_ids"], "reused modules belong to both tracks"
    assert c.get(f"/api/modules/{gid}/01-intro").json()["markdown"].startswith("# Hello")
    assert c.post(f"/api/modules/{gid}/01-intro/done").json()["done"] is True
    assert next(x for x in c.get("/api/curricula").json() if x["id"] == "my-pack")["progress"]["done"] == 1
    assert c.post(f"/api/whiteboard/{gid}/01-intro", json={"score": 4}).status_code == 200


def test_private_overlay_curricula_and_unclaimed_private_modules(tmp_path, monkeypatch):
    priv = tmp_path / "priv"
    monkeypatch.setenv("DRILLPAD_PRIVATE_DIR", str(priv))
    d = write_curriculum(priv / "curricula", "secret-track", "      - module: notes\n")
    write_module(d, "notes")
    stray = priv / "modules" / "loose-notes"
    (stray / "lessons").mkdir(parents=True)
    (stray / "module.yaml").write_text('id: loose-notes\ntitle: "Loose"\nlanguage: systems\ndescription: "d"\nlessons:\n- id: 01-a\n  title: "A"\n  practice: []\n')
    c = TestClient(create_app(tmp_path / "t.db"))
    cs = {x["id"]: x for x in c.get("/api/curricula").json()}
    assert cs["secret-track"]["source"] == "private" and cs["private"]["levels"][0]["units"][0]["module_id"] == "loose-notes"
    ids = list(cs)
    assert ids.index("core") < ids.index("secret-track") < ids.index("private"), "private tracks sort last"
    mods = {m["id"]: m for m in c.get("/api/modules").json()}
    assert mods["secret-track.notes"]["private"] is True


def test_broken_curriculum_is_skipped_not_fatal(tmp_path, monkeypatch):
    pack = tmp_path / "pack"
    (pack / "bad").mkdir(parents=True)
    (pack / "bad" / "curriculum.yaml").write_text("id: [not, a, string\n")
    monkeypatch.setenv("DRILLPAD_CURRICULA_PATH", str(pack))
    c = TestClient(create_app(tmp_path / "t.db"))
    assert c.get("/api/curricula").status_code == 200 and c.get("/api/modules").status_code == 200


# ---- scaffolding via scripts/course.py
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("course", Path(__file__).parent.parent / "scripts" / "course.py")
course = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(course)


class _A:
    def __init__(self, **kw):
        self.__dict__.update({"private": False, "dest": None, "curriculum": None, "level": None, "stage": None,
                              "title": None, "language": "systems", **kw})


def test_new_private_curriculum_then_module_then_lesson_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("DRILLPAD_PRIVATE_DIR", str(tmp_path / "priv"))
    assert course.cmd_new_curriculum(_A(id="my-notes", title="My Notes", private=True)) == 0
    root = tmp_path / "priv" / "curricula" / "my-notes"
    assert (root / "curriculum.yaml").exists()
    with pytest.raises(SystemExit, match="already exists"):
        course.cmd_new_curriculum(_A(id="my-notes", title="again", private=True))
    assert course.cmd_new_module(_A(id="first-topic", curriculum="my-notes", stage="First Topic")) == 0
    assert course.cmd_new_module(_A(id="second-topic", curriculum="my-notes", title="Second Topic")) == 0
    text = (root / "curriculum.yaml").read_text()
    assert "- module: first-topic" in text and "- module: second-topic" in text and "units: []" not in text
    assert text.index("first-topic") < text.index("second-topic")

    class L:
        module, slug, title = "my-notes.first-topic", "intro", "Intro"

    assert course.cmd_new_lesson(L) == 0
    assert (root / "modules" / "first-topic" / "lessons" / "01-intro.md").exists()
    c = TestClient(create_app(tmp_path / "t.db"))
    cs = {x["id"]: x for x in c.get("/api/curricula").json()}
    units = {u["key"]: u for lv in cs["my-notes"]["levels"] for u in lv["units"]}
    assert units["first-topic"]["status"] == "ready" and units["first-topic"]["lessons"] == 1
    assert units["second-topic"]["status"] == "ready" and units["second-topic"]["lessons"] == 0


def test_starting_a_planned_module_does_not_duplicate_its_unit(tmp_path, monkeypatch):
    monkeypatch.setenv("DRILLPAD_PRIVATE_DIR", str(tmp_path / "priv"))
    d = write_curriculum(tmp_path / "priv" / "curricula", "plan-track",
                         "      - module: later-one\n        title: Later One\n        summary: Planned for later.\n")
    assert course.cmd_new_module(_A(id="later-one", curriculum="plan-track")) == 0
    assert (d / "curriculum.yaml").read_text().count("later-one") == 1
    assert "Planned for later." in (d / "modules" / "later-one" / "module.yaml").read_text()
    with pytest.raises(SystemExit, match="already exists"):
        course.cmd_new_module(_A(id="later-one", curriculum="plan-track"))


def test_insert_unit_goes_at_the_end_of_the_named_level(tmp_path):
    text = ('id: x\nlevels:\n  - id: one\n    title: One\n    units:\n      - module: a\n        title: A\n'
            '  - id: two\n    title: Two\n    units: []\ncapstones: []\n')
    out = course.insert_unit(text, "one", ["      - module: b", '        title: "B"'])
    assert out.index("module: b") < out.index("- id: two") and out.index("module: a") < out.index("module: b")
    out2 = course.insert_unit(text, "two", ["      - module: c", '        title: "C"'])
    assert "units:\n      - module: c" in out2 and out2.index("module: c") < out2.index("capstones")


def test_standalone_pack_scaffold_can_be_plugged_in(tmp_path, monkeypatch):
    pack = tmp_path / "my-pack-repo"
    assert course.cmd_new_curriculum(_A(id="my-pack", title="My Pack", dest=str(pack))) == 0
    assert (pack / "README.md").exists() and (pack / "curriculum.yaml").exists()
    monkeypatch.setenv("DRILLPAD_CURRICULA_PATH", str(pack))
    assert course.cmd_new_module(_A(id="alpha", curriculum="my-pack", stage="Alpha")) == 0
    c = TestClient(create_app(tmp_path / "t.db"))
    assert any(x["id"] == "my-pack" and x["source"] == "external" for x in c.get("/api/curricula").json())
    with pytest.raises(SystemExit, match="not empty"):
        course.cmd_new_curriculum(_A(id="other-pack", title="x", dest=str(pack)))
