from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from drillpad.web.app import create_app

MID, LID = "reasoning-under-constraints", "01-cpu-cycles-and-hardware"


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "t.db"))


def ago(days: float) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def test_empty_overview(client):
    o = client.get("/api/whiteboard").json()
    assert o["lessons"] == {} and o["due"] == []
    assert o["summary"]["whiteboarded"] == 0 and o["summary"]["mean_last_score"] is None
    assert o["summary"]["total_lessons"] > 100
    d = client.get(f"/api/whiteboard/{MID}/{LID}").json()
    assert d["state"] is None and d["history"] == []


def test_log_session_schedules_next_review(client):
    r = client.post(f"/api/whiteboard/{MID}/{LID}", json={"score": 4, "notes": "forgot the TLB case"}).json()
    st = r["state"]
    assert st["sessions"] == 1 and st["last_score"] == 4 and not st["due_now"]
    assert datetime.fromisoformat(st["due"]) > datetime.now(UTC)
    assert r["history"][0]["notes"] == "forgot the TLB case"
    o = client.get("/api/whiteboard").json()
    assert o["summary"]["whiteboarded"] == 1 and o["summary"]["mean_last_score"] == 4


def test_low_score_comes_due_sooner_than_high_score(client):
    other = "02-memory-bandwidth-roofline"
    client.post(f"/api/whiteboard/{MID}/{LID}", json={"score": 1})
    client.post(f"/api/whiteboard/{MID}/{other}", json={"score": 5})
    lessons = client.get("/api/whiteboard").json()["lessons"]
    assert lessons[f"{MID}/{LID}"]["due"] < lessons[f"{MID}/{other}"]["due"]


def test_backfilled_session_can_make_a_lesson_due(client):
    client.post(f"/api/whiteboard/{MID}/{LID}", json={"score": 2, "at": ago(30)})
    o = client.get("/api/whiteboard").json()
    assert o["summary"]["due_now"] == 1
    assert o["due"][0]["lesson"] == LID and o["due"][0]["title"]


def test_delete_rebuilds_schedule_from_remaining_sessions(client):
    client.post(f"/api/whiteboard/{MID}/{LID}", json={"score": 5, "at": ago(10)})
    bad = client.post(f"/api/whiteboard/{MID}/{LID}", json={"score": 1}).json()["history"][0]["id"]
    after_bad = client.get(f"/api/whiteboard/{MID}/{LID}").json()["state"]
    d = client.delete(f"/api/whiteboard/sessions/{bad}").json()
    assert d["state"]["sessions"] == 1 and d["state"]["last_score"] == 5
    assert d["state"]["due"] != after_bad["due"]
    only = d["history"][0]["id"]
    d = client.delete(f"/api/whiteboard/sessions/{only}").json()
    assert d["state"] is None and client.get("/api/whiteboard").json()["lessons"] == {}


def test_replay_is_deterministic(client):
    for score, days in [(3, 12), (4, 6), (2, 1)]:
        client.post(f"/api/whiteboard/{MID}/{LID}", json={"score": score, "at": ago(days)})
    a = client.get(f"/api/whiteboard/{MID}/{LID}").json()["state"]["due"]
    b = client.get(f"/api/whiteboard/{MID}/{LID}").json()["state"]["due"]
    assert a == b


def test_validation(client):
    assert client.post(f"/api/whiteboard/{MID}/{LID}", json={"score": 0}).status_code == 422
    assert client.post(f"/api/whiteboard/{MID}/{LID}", json={"score": 6}).status_code == 422
    assert client.post(f"/api/whiteboard/{MID}/{LID}", json={"score": 3, "at": "not-a-date"}).status_code == 422
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    assert client.post(f"/api/whiteboard/{MID}/{LID}", json={"score": 3, "at": future}).status_code == 422
    assert client.post("/api/whiteboard/nope/x", json={"score": 3}).status_code == 404
    assert client.get(f"/api/whiteboard/{MID}/nope").status_code == 404
    assert client.delete("/api/whiteboard/sessions/999").status_code == 404
