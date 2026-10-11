from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from drillpad.core import db
from drillpad.srs import engine as srs
from drillpad.web.app import create_app

T0 = datetime(2026, 10, 1, 12, tzinfo=UTC)


def test_review_is_idempotent_per_attempt_and_recall_decays(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    a = db.start_attempt(conn, "two-sum")
    assert srs.review(conn, "two-sum", a, 3, "pass", T0)
    assert not srs.review(conn, "two-sum", a, 1, "stuck", T0)  # same attempt never counts twice
    early = srs.snapshot(conn, T0 + timedelta(hours=1))["two-sum"]
    late = srs.snapshot(conn, T0 + timedelta(days=30))["two-sum"]
    assert early["retrievability"] > late["retrievability"]
    assert late["due_now"] and early["reviews"] == 1


def test_again_lowers_stability_vs_easy(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    for pid, ease in (("a", 1), ("b", 4)):
        srs.review(conn, pid, db.start_attempt(conn, pid), ease, "pass", T0)
    snap = srs.snapshot(conn, T0 + timedelta(days=3))
    assert snap["b"]["retrievability"] > snap["a"]["retrievability"]


def test_reviews_append_only(tmp_path):
    import sqlite3
    conn = db.connect(tmp_path / "t.db")
    srs.review(conn, "x", db.start_attempt(conn, "x"), 3, "pass", T0)
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM srs_reviews")


@pytest.fixture
def client(tmp_path, monkeypatch):
    from drillpad.web import plan as plan_mod
    monkeypatch.setenv("DRILLPAD_ANKI_URL", "http://127.0.0.1:9")
    plan_mod._anki_cache.update(t=0.0, ids=set(), ok=None)
    return TestClient(create_app(tmp_path / "t.db"))


def test_pass_and_stuck_log_reviews_and_surface_in_api(client):
    from tests.test_core import SOLUTION
    a = client.post("/api/attempts", json={"problem_id": "dynamic-array"}).json()["attempt_id"]
    client.post(f"/api/attempts/{a}/run", json={"code": SOLUTION})
    client.post(f"/api/attempts/{a}/run", json={"code": SOLUTION})  # second pass in same attempt: no extra review
    b = client.post("/api/attempts", json={"problem_id": "stack"}).json()["attempt_id"]
    client.post(f"/api/attempts/{b}/solution", json={"reason": "stuck"})
    q = client.get("/api/questions").json()
    items = {i["id"]: i for lv in q["levers"] for g in lv["groups"] for i in g["items"]} | {e["id"]: e for e in q["extras"]}
    assert items["dynamic-array"]["recall"] is not None and items["stack"]["recall"] is not None
    plan = client.get("/api/plan").json()
    assert "due_reviews" in plan
    from drillpad.web.app import create_app  # noqa: F401
    snap = client.get("/api/plan").json()
    assert snap["picks"]


def test_planner_prefers_due_review_over_fresh_pass():
    from drillpad.content.loader import load_all
    from drillpad.evaluation.engine import Fractions
    from drillpad.evaluation.firms import load_profiles
    from drillpad.planner import engine
    from drillpad.planner import settings as st

    ps = load_all()
    ev = {pid: {"fr": Fractions({d: 1.0 for d in ("correctness", "edge_cases", "complexity", "pace", "communication", "extensions", "quality")}, {})}
          for pid in ("two-sum", "stack")}
    snap = {"two-sum": {"retrievability": 0.55, "due_now": True, "days_since": 20.0},
            "stack": {"retrievability": 0.99, "due_now": False, "days_since": 0.0}}
    now = datetime(2026, 10, 6, tzinfo=UTC)
    out = engine.build(st.Settings(session_minutes=240), ps, load_profiles(), ev, {}, {}, set(), {}, now, None, srs_snapshot=snap)
    order = [p["problem_id"] for p in out["picks"]]
    assert "two-sum" in order and any("Due for review" in r for p in out["picks"] if p["problem_id"] == "two-sum" for r in p["reasons"])
    assert out["due_reviews"][0]["problem_id"] == "two-sum"


def test_planner_uses_recall_even_without_a_scored_evaluation():
    from drillpad.content.loader import load_all
    from drillpad.evaluation.firms import load_profiles
    from drillpad.planner import engine
    from drillpad.planner import settings as st

    snap = {"two-sum": {"retrievability": 0.5, "due_now": True, "days_since": 25.0}}
    out = engine.build(st.Settings(session_minutes=240), load_all(), load_profiles(), {}, {}, {}, set(), {},
                       datetime(2026, 10, 6, tzinfo=UTC), None, srs_snapshot=snap)
    pick = next(p for p in out["picks"] if p["problem_id"] == "two-sum")
    assert any("Due for review" in r for r in pick["reasons"]) and "Not attempted yet" not in pick["reasons"]
