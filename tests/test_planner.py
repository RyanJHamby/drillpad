from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from drillpad.content.loader import load_all
from drillpad.evaluation.firms import load_profiles
from drillpad.planner import engine
from drillpad.planner import settings as st
from drillpad.web.app import create_app

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


def run(s, **kw):
    kw.setdefault("latest_evals", {})
    return engine.build(s, load_all(), load_profiles(), kw.pop("latest_evals"), {}, {}, set(), {}, NOW, kw.pop("minutes", None))


def test_urgency_ramps_and_expires():
    assert engine.urgency_factor(None, True) == 1.0
    assert engine.urgency_factor(14, True) == 1.0
    assert engine.urgency_factor(0, True) == 3.0
    assert engine.urgency_factor(7, True) == pytest.approx(2.0)
    assert engine.urgency_factor(0, False) == 1.0


def test_category_knob_changes_queue():
    base = st.Settings(firm_vs_pattern=0, chase_gaps=50)
    base.categories = st._cats("leetcode")
    a = run(base)
    base.categories = st._cats("systems-impl")
    b = run(base)
    cats_a = {c for p in a["picks"][:3] for c in p["categories"]}
    cats_b = {c for p in b["picks"][:3] for c in p["categories"]}
    assert "leetcode" in cats_a and "systems-impl" in cats_b
    assert a["picks"][0]["problem_id"] != b["picks"][0]["problem_id"] or cats_a != cats_b


def test_firm_vs_pattern_knob_and_urgent_firm_wins():
    s = st.Settings(firm_vs_pattern=100)
    s.firms = [st.FirmSlot("generic-ai-lab", (date(2026, 10, 8)).isoformat(), 100)]
    out = run(s)
    ids = [p["problem_id"] for p in out["picks"]]
    assert set(ids[:3]) <= set(load_profiles()["generic-ai-lab"].problem_ids) or any("generic ai lab" in r.lower() or load_profiles()["generic-ai-lab"].name in r for p in out["picks"][:3] for r in p["reasons"])
    assert out["firms"][0]["days"] == 2 and out["firms"][0]["urgency"] > 2
    assert out["mock"] and out["mock"]["firm"] == load_profiles()["generic-ai-lab"].name


def test_expired_and_inactive_firms_ignored():
    s = st.Settings(firm_vs_pattern=100)
    s.firms = [st.FirmSlot("generic-ai-lab", "2026-09-01", 100), st.FirmSlot("generic-quant", None, 100, active=False)]
    assert run(s)["firms"] == []


def test_budget_respected_and_reasons_present():
    out = run(st.Settings(session_minutes=45))
    assert out["picks"] and all(p["reasons"] for p in out["picks"])
    assert out["planned_minutes"] <= 45 + max(p["minutes"] for p in out["picks"])  # first pick may exceed
    assert len({p["problem_id"] for p in out["picks"]}) == len(out["picks"])


def test_presets_apply_partially():
    s = st.apply_preset(st.Settings(session_minutes=90), "trading-style")
    assert s.categories["trading"] == 100 and s.session_minutes == 90 and s.firm_vs_pattern == 20


@pytest.fixture
def client(tmp_path, monkeypatch):
    from drillpad.web import plan as plan_mod
    monkeypatch.setenv("DRILLPAD_ANKI_URL", "http://127.0.0.1:9")  # never touch the real Anki in tests
    plan_mod._anki_cache.update(t=0.0, ids=set(), ok=None)
    return TestClient(create_app(tmp_path / "t.db"))


def test_api_roundtrip(client):
    r = client.get("/api/plan").json()
    assert r["picks"] and r["presets"] and isinstance(r["firm_options"], list)  # empty in a public copy: only generic profiles ship
    body = r["settings"] | {"firms": [{"id": "generic-quant", "date": (datetime.now(UTC).date() + timedelta(days=5)).isoformat(), "weight": 80}],
                            "firm_vs_pattern": 90}
    r2 = client.put("/api/plan/settings", json=body).json()
    assert r2["settings"]["firm_vs_pattern"] == 90 and r2["firms"][0]["id"] == "generic-quant"
    assert client.put("/api/plan/settings", json={"firms": [{"id": "nope"}]}).status_code == 400
    assert client.post("/api/plan/preset", json={"id": "leetcode-style"}).json()["settings"]["categories"]["leetcode"] == 100


def test_forced_recall_after_stuck(client):
    aid = client.post("/api/attempts", json={"problem_id": "dynamic-array"}).json()["attempt_id"]
    client.post(f"/api/attempts/{aid}/solution", json={"reason": "stuck"})
    top = client.get("/api/plan").json()["picks"][0]
    assert top["problem_id"] == "dynamic-array" and top["forced"] and "retry from memory" in top["reasons"][0]
