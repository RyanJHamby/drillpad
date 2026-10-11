import sqlite3
import time
from pathlib import Path

from drillpad.core import paths
from drillpad.web import backup


def make_db(path: Path, value: str = "a") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE IF NOT EXISTS t(v TEXT)")
    c.execute("INSERT INTO t VALUES (?)", (value,))
    c.commit()
    c.close()


def test_paths_follow_env_overrides(tmp_path, monkeypatch):
    assert paths.data_dir() == tmp_path / "data-dir"
    assert paths.db_path() == tmp_path / "data-dir" / "drillpad.db"
    assert paths.private_dir() == tmp_path / "data-dir" / "private"
    monkeypatch.setenv("DRILLPAD_DB", str(tmp_path / "x.db"))
    monkeypatch.setenv("DRILLPAD_PRIVATE_DIR", str(tmp_path / "priv"))
    assert paths.db_path() == tmp_path / "x.db" and paths.private_dir() == tmp_path / "priv"


def test_legacy_db_is_copied_once_and_never_deleted(tmp_path):
    legacy, target = tmp_path / "old" / "drillpad.db", tmp_path / "new" / "drillpad.db"
    make_db(legacy)
    assert paths.migrate_legacy_db(target, legacy) is True
    assert legacy.exists() and target.exists()
    make_db(target, "newer")
    assert paths.migrate_legacy_db(target, legacy) is False, "must not overwrite an existing database"
    assert sqlite3.connect(target).execute("SELECT count(*) FROM t").fetchone()[0] == 2


def test_backup_is_consistent_rotates_and_skips_when_unchanged(tmp_path):
    db = tmp_path / "d" / "drillpad.db"
    make_db(db)
    first = backup.backup_database(db, keep=2)
    assert first and sqlite3.connect(first).execute("SELECT v FROM t").fetchall() == [("a",)]
    assert backup.backup_database(db, keep=2) is None, "no writes since the last snapshot"
    for i in range(3):
        time.sleep(0.05)
        make_db(db, f"v{i}")
        assert backup.backup_database(db, keep=2)
    kept = sorted((tmp_path / "d" / "backups").glob("drillpad-*.db"))
    assert len(kept) == 2
    assert sqlite3.connect(kept[-1]).execute("SELECT v FROM t").fetchall()[-1] == ("v2",), "newest snapshots are kept"


def test_offsite_copy_and_unplugged_drive_does_not_raise(tmp_path):
    db = tmp_path / "d" / "drillpad.db"
    make_db(db)
    off = tmp_path / "icloud"
    dest = backup.backup_database(db, offsite_dir=off)
    assert (off / dest.name).exists()
    make_db(db, "b")
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    assert backup.backup_database(db, offsite_dir=blocker / "sub") is not None  # warns, local snapshot still made


def test_backup_never_touches_git(tmp_path):
    db = tmp_path / "repo" / "drillpad.db"
    make_db(db)
    (tmp_path / "repo" / ".git").mkdir()
    backup.backup_database(db)
    assert not any((tmp_path / "repo" / ".git").iterdir())


def _write_private_module(root: Path, mid: str, lesson_text: str = "# Private lesson\nbody\n") -> None:
    mod = root / "modules" / mid
    (mod / "lessons").mkdir(parents=True)
    (mod / "module.yaml").write_text(f'id: {mid}\ntitle: "Private {mid}"\nlanguage: systems\ndescription: "d"\n'
                                     'lessons:\n- id: 01-x\n  title: "X"\n  practice: []\n')
    (mod / "lessons" / "01-x.md").write_text(lesson_text)


def test_private_overlay_modules_load_work_with_progress_and_never_shadow_bundled(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from drillpad.web.app import create_app

    priv = tmp_path / "priv"
    monkeypatch.setenv("DRILLPAD_PRIVATE_DIR", str(priv))
    _write_private_module(priv, "my-firm-prep")
    _write_private_module(priv, "reasoning-under-constraints")  # collides with a bundled id
    client = TestClient(create_app(tmp_path / "t.db"))
    mods = {m["id"]: m for m in client.get("/api/modules").json()}
    assert mods["my-firm-prep"]["stage_id"] == "99-private" and mods["my-firm-prep"]["private"] is True
    assert "private" not in mods["reasoning-under-constraints"], "bundled module must win a clash"
    assert client.get("/api/modules/my-firm-prep/01-x").json()["markdown"].startswith("# Private lesson")
    assert client.post("/api/whiteboard/my-firm-prep/01-x", json={"score": 3}).status_code == 200
    ids = [m["id"] for m in client.get("/api/modules").json()]
    assert ids.index("my-firm-prep") == len(ids) - 1, "private modules sort after every bundled stage"


def test_private_firm_profiles_override_bundled(tmp_path, monkeypatch):
    from drillpad.evaluation.firms import load_profiles

    priv = tmp_path / "priv"
    (priv / "firms").mkdir(parents=True)
    bundled = (Path(__file__).parent.parent / "src/drillpad/content/firms/generic-quant.yaml").read_text()
    (priv / "firms" / "mine.yaml").write_text(bundled.replace("id: generic-quant", "id: mine", 1))
    monkeypatch.setenv("DRILLPAD_PRIVATE_DIR", str(priv))
    assert "mine" in load_profiles()
    monkeypatch.setenv("DRILLPAD_PRIVATE_DIR", str(tmp_path / "none"))
    assert "mine" not in load_profiles()
