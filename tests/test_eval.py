import json

import pytest
from fastapi.testclient import TestClient

from drillpad.core import db
from drillpad.core.models import Complexity, Extension, Problem, TestCase
from drillpad.evaluation import bigo, engine
from drillpad.evaluation.firms import GENERIC, load_profiles
from drillpad.web.app import create_app


def test_bigo_normalisation():
    assert bigo.score("O(1)", "O(1)") == 1
    assert bigo.score("o( n log n )", "O(n log n)") == 1
    assert bigo.score("O(n*logn)", "O(n log n)") == 1
    assert bigo.score("O(n²)", "O(n^2)") == 1
    assert bigo.score("O(n)", "O(1)") == 0
    assert bigo.score("", "O(1)") == 0
    assert bigo.score("O(1)", "O(1) amortized") == 0.7  # right core, missing qualifier
    assert bigo.score("O(1) amortized", "O(1) amortized") == 1
    assert bigo.score("O(1)", "O(1) amortized", ["O(1)"]) == 1


def mkrows(conn, aid, runs):
    for code, results, passed in runs:
        db.add_revision(conn, aid, code, passed, json.dumps(results), 5)
    return db.revisions(conn, aid)


def test_engine_scores_and_floors(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    p = Problem(
        id="p", title="t", statement="", starter="", bar_level=1, target_minutes=10,
        tests=[TestCase("a", "", False, ["empty"]), TestCase("b", "", True, ["boundary"])],
        complexity=[Complexity("get", "O(1)", "O(n)")],
        extensions=[Extension("q", ["x", "y"])],
    )
    aid = db.start_attempt(conn, "p")
    started = conn.execute("SELECT started_at FROM attempts").fetchone()[0]
    res_bad = [{"name": "a", "passed": True, "hidden": False}, {"name": "b", "passed": False, "hidden": True}]
    res_ok = [{"name": "a", "passed": True, "hidden": False}, {"name": "b", "passed": True, "hidden": True}]
    rows = mkrows(conn, aid, [("c1", res_bad, False), ("c2", res_ok, True)])
    fr = engine.raw_fractions(p, rows, started, GENERIC, {"get": {"time": "O(1)", "space": "O(n)"}},
                              [{"idx": 0, "covered": [True, False]}], None)
    assert fr.dims["correctness"] == 1.0
    assert fr.dims["edge_cases"] == pytest.approx(0.5 * 0.5 + 0.5 * 1.0)  # first run missed 'boundary'
    assert fr.dims["complexity"] == 1.0
    assert fr.dims["extensions"] == 0.5
    assert fr.dims["communication"] is None
    assert fr.dims["quality"] == 0.75  # passed on 2nd run
    s = engine.apply_profile(fr, GENERIC)
    assert "communication" in s.unassessed
    assert s.per_dim["communication"]["earned"] == 0  # conservative
    assert any("boundary" in f["why"] for f in s.fixes if f["dimension"] == "edge_cases")
    # same attempt, never-complexity answer -> floor violation
    fr2 = engine.raw_fractions(p, rows, started, GENERIC, {}, [], None)
    s2 = engine.apply_profile(fr2, GENERIC)
    assert s2.verdict == "NO-PASS" and any("complexity" in f for f in s2.failed_floors)


def test_all_firm_profiles_load():
    profiles = load_profiles()
    assert "generic" in profiles
    for p in profiles.values():
        assert sum(p.weights.values()) == 100


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "t.db"))


def test_api_evaluate_and_progress(client):
    from tests.test_core import SOLUTION

    prob = client.get("/api/problems/dynamic-array").json()
    assert "complexity_ops" in prob and all("key_points" not in e for e in prob["extensions"])
    aid = client.post("/api/attempts", json={"problem_id": "dynamic-array"}).json()["attempt_id"]
    client.post(f"/api/attempts/{aid}/run", json={"code": SOLUTION})
    r = client.post(f"/api/attempts/{aid}/evaluate", json={"firm_id": "generic"}).json()
    assert r["score"]["verdict"] == "NO-PASS"  # nothing submitted for complexity/extensions/communication
    pr = client.get("/api/progress?firm=generic").json()
    assert pr["evaluations"] == 1 and pr["firm"]["evaluated"] == 1 and not pr["firm"]["ready"]
    assert pr["next"] and "definition" in pr
    assert client.get("/api/firms").json()[0]["id"]


def test_evaluations_append_only(tmp_path):
    import sqlite3
    conn = db.connect(tmp_path / "t.db")
    aid = db.start_attempt(conn, "x")
    engine.store_evaluation(conn, aid, "x", engine.Fractions({}, {}), {})
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM evaluations")


def test_solution_gating_and_give_up(client):
    from tests.test_core import SOLUTION

    aid = client.post("/api/attempts", json={"problem_id": "dynamic-array"}).json()["attempt_id"]
    assert client.post(f"/api/attempts/{aid}/solution", json={"reason": "passed"}).status_code == 409
    client.post(f"/api/attempts/{aid}/run", json={"code": SOLUTION})
    ok = client.post(f"/api/attempts/{aid}/solution", json={"reason": "passed"})
    assert ok.status_code == 200 and "class DynamicArray" in ok.json()["solution"]
    assert not ok.json()["gave_up"]

    aid2 = client.post("/api/attempts", json={"problem_id": "dynamic-array"}).json()["attempt_id"]
    assert client.post(f"/api/attempts/{aid2}/solution", json={"reason": "stuck"}).json()["gave_up"]
    client.post(f"/api/attempts/{aid2}/run", json={"code": SOLUTION})  # pasted after peeking
    r = client.post(f"/api/attempts/{aid2}/evaluate", json={}).json()
    assert r["detail"]["gave_up"] is True
    assert r["dims"]["pace"] == 0 and r["dims"]["quality"] == 0
    assert r["dims"]["correctness"] == 0  # post-peek runs do not count
    s = client.get(f"/api/attempts/{aid2}/anki").json()
    assert s["ease"] == 1 and s["label"] == "Again"
    assert client.get(f"/api/attempts/{aid}/anki").json()["ease"] in (2, 3, 4)
