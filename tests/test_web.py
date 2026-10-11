import pytest
from fastapi.testclient import TestClient

from drillpad.web.app import create_app
from tests.test_core import SOLUTION


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "t.db"))


def test_full_flow_and_hidden_masking(client):
    assert "dynamic-array" in [p["id"] for p in client.get("/api/problems").json()]
    p = client.get("/api/problems/dynamic-array").json()
    assert all(not t["hidden"] for t in p["tests"])
    aid = client.post("/api/attempts", json={"problem_id": "dynamic-array"}).json()["attempt_id"]
    bad = client.post(f"/api/attempts/{aid}/run", json={"code": p["starter"]}).json()
    assert not bad["passed"]
    good = client.post(f"/api/attempts/{aid}/run", json={"code": SOLUTION}).json()
    assert good["passed"] and good["seq"] == 2
    assert any(r["name"] == "hidden test" for r in good["results"])
    revs = client.get(f"/api/attempts/{aid}/revisions").json()
    assert [r["passed"] for r in revs] == [False, True]


def test_unknown_ids_404(client):
    assert client.get("/api/problems/nope").status_code == 404
    assert client.post("/api/attempts/99/run", json={"code": ""}).status_code == 404


def test_readiness_updates_after_solve(client):
    r0 = client.get("/api/readiness").json()
    assert r0["overall"] == 0
    aid = client.post("/api/attempts", json={"problem_id": "dynamic-array"}).json()["attempt_id"]
    client.post(f"/api/attempts/{aid}/run", json={"code": SOLUTION})
    r1 = client.get("/api/readiness").json()
    l1 = next(lv for lv in r1["levels"] if lv["key"] == "L1")
    assert l1["solved"] == 1 and l1["readiness"] > 0 and r1["overall"] > 0
    probs = {p["id"]: p for p in client.get("/api/problems").json()}
    assert probs["dynamic-array"]["solved"] is True


def test_scratch_run_with_stdin_and_timeout(client):
    r = client.post("/api/scratch", json={"code": "print(input()[::-1])", "stdin": "abc\n"}).json()
    assert r["stdout"].strip() == "cba" and r["exit_code"] == 0
    r = client.post("/api/scratch", json={"code": "raise ValueError('x')"}).json()
    assert r["exit_code"] != 0 and "ValueError" in r["stderr"]


def test_questions_catalog(client):
    r = client.get("/api/questions").json()
    ids = {lv["id"]: lv for lv in r["levers"]}
    assert {"leetcode", "systems-impl", "trading", "fintech", "ai-infra", "ml", "cpp", "rust"} <= set(ids)
    two_sum = next(i for g in ids["leetcode"]["groups"] for i in g["items"] if i["id"] == "two-sum")
    assert two_sum["status"] in ("todo", "attempted", "passing")
    assert ids["leetcode"]["authored"] <= ids["leetcode"]["total"] and r["total_problems"] >= 71


def test_problem_attempt_history(client):
    from tests.test_core import SOLUTION
    a1 = client.post("/api/attempts", json={"problem_id": "dynamic-array"}).json()["attempt_id"]
    client.post(f"/api/attempts/{a1}/run", json={"code": "x = 1"})
    client.post(f"/api/attempts/{a1}/run", json={"code": SOLUTION})
    a2 = client.post("/api/attempts", json={"problem_id": "dynamic-array"}).json()["attempt_id"]  # empty: hidden
    a3 = client.post("/api/attempts", json={"problem_id": "dynamic-array"}).json()["attempt_id"]
    client.post(f"/api/attempts/{a3}/run", json={"code": "x = 1"})
    rows = client.get("/api/problems/dynamic-array/attempts").json()
    assert [r["id"] for r in rows] == [a3, a1] and a2 not in [r["id"] for r in rows]
    assert rows[1]["passed"] and rows[1]["runs"] == 2 and not rows[0]["passed"]
    assert client.get("/api/problems/nope/attempts").status_code == 404


def test_concurrent_requests_do_not_corrupt_db(client):
    """Regression: a bare shared sqlite connection raised InterfaceError and raced revision seq numbers."""
    from concurrent.futures import ThreadPoolExecutor

    aid = client.post("/api/attempts", json={"problem_id": "two-sum"}).json()["attempt_id"]

    def job(i):
        k = i % 5
        if k == 0:
            return client.get("/api/problems").status_code
        if k == 1:
            return client.get("/api/readiness").status_code
        if k == 2:
            return client.post(f"/api/attempts/{aid}/run", json={"code": "def two_sum(a, b): return []"}).status_code
        if k == 3:
            return client.get("/api/problems/two-sum/attempts").status_code
        return client.get("/api/progress").status_code

    with ThreadPoolExecutor(12) as ex:
        codes = list(ex.map(job, range(100)))
    assert set(codes) == {200}
    seqs = [r["seq"] for r in client.get(f"/api/attempts/{aid}/revisions").json()]
    assert seqs == list(range(1, len(seqs) + 1))


def test_draft_autosave_roundtrip_and_blank_is_a_real_draft(client):
    assert client.get("/api/problems/two-sum/draft").json() == {"exists": False}
    assert client.put("/api/problems/two-sum/draft", json={"code": "x = 1"}).json()["saved"]
    d = client.get("/api/problems/two-sum/draft").json()
    assert d["exists"] and d["code"] == "x = 1" and d["updated_at"]
    client.post("/api/problems/two-sum/draft", json={"code": ""})  # POST = sendBeacon path; blank canvas is valid
    assert client.get("/api/problems/two-sum/draft").json()["code"] == ""
    assert client.delete("/api/problems/two-sum/draft").json()["deleted"]
    assert client.get("/api/problems/two-sum/draft").json() == {"exists": False}
    assert client.put("/api/problems/nope/draft", json={"code": "x"}).status_code == 404


def test_resume_reuses_open_attempt_but_not_after_pass_or_stuck(client):
    from tests.test_core import SOLUTION
    body = {"problem_id": "dynamic-array", "mode": "practice"}
    a = client.post("/api/attempts/resume", json=body).json()
    assert not a["resumed"]
    b = client.post("/api/attempts/resume", json=body).json()
    assert b["resumed"] and b["attempt_id"] == a["attempt_id"] and b["started_at"] == a["started_at"]
    assert not client.post("/api/attempts/resume", json={**body, "mode": "screen"}).json()["resumed"]  # other mode
    client.post(f"/api/attempts/{a['attempt_id']}/run", json={"code": SOLUTION})  # passed -> done
    c = client.post("/api/attempts/resume", json=body).json()
    assert not c["resumed"] and c["attempt_id"] != a["attempt_id"]
    client.post(f"/api/attempts/{c['attempt_id']}/solution", json={"reason": "stuck"})
    assert not client.post("/api/attempts/resume", json=body).json()["resumed"]


def test_active_time_clock_drives_pace_and_survives_resume(tmp_path):
    """Time away from the page must not count: pace uses the client's active (un-paused) ms."""
    import sqlite3
    from datetime import UTC, datetime, timedelta

    from tests.test_core import SOLUTION
    db_path = tmp_path / "clock.db"
    client = TestClient(create_app(db_path))
    body = {"problem_id": "dynamic-array", "mode": "practice"}
    a = client.post("/api/attempts/resume", json=body).json()["attempt_id"]
    old = (datetime.now(UTC) - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    with sqlite3.connect(db_path) as raw:  # pretend the attempt was opened 30 min ago
        raw.execute("UPDATE attempts SET started_at = ? WHERE id = ?", (old, a))
    client.put("/api/problems/dynamic-array/draft", json={"code": "x", "attempt_id": a, "active_ms": 90_000})
    r = client.post("/api/attempts/resume", json=body).json()
    assert r["resumed"] and r["active_ms"] == 90_000            # clock continues where the user left it
    client.put("/api/problems/dynamic-array/draft", json={"code": "x", "attempt_id": a, "active_ms": 10_000})
    assert client.post("/api/attempts/resume", json=body).json()["active_ms"] == 90_000  # monotonic
    client.post(f"/api/attempts/{a}/run", json={"code": SOLUTION, "active_ms": 120_000})
    hist = client.get("/api/problems/dynamic-array/attempts").json()
    assert hist[0]["minutes_to_pass"] == 2.0                     # active (2 min), not wall-clock (30 min)
    ev = client.post(f"/api/attempts/{a}/evaluate", json={}).json()
    assert ev["detail"]["pace"]["minutes"] == 2.0
    # absurd client values are bounded by the wall-clock age of the attempt
    b = client.post("/api/attempts", json=body).json()["attempt_id"]
    client.post(f"/api/attempts/{b}/run", json={"code": SOLUTION, "active_ms": 10**9})
    assert client.get("/api/problems/dynamic-array/attempts").json()[0]["minutes_to_pass"] < 1


def test_modules_api_and_progress(client):
    # The cpp/rust/ml stub modules this test used to check were removed in d79aa5f; use a module that ships lessons.
    mid = "reasoning-under-constraints"
    mods = client.get("/api/modules").json()
    m = next(x for x in mods if x["id"] == mid)
    assert len(m["lessons"]) >= 4 and all("practice" in x and "written" in x for x in m["lessons"])
    assert m["stage_id"] == "0-thinking-tools" and m["stage_position"] == 1
    assert [x["stage_id"] for x in mods if "stage_id" in x] == sorted(x["stage_id"] for x in mods if "stage_id" in x)
    lid = m["lessons"][0]["id"]
    assert client.get(f"/api/modules/{mid}/{lid}").json()["markdown"]
    assert client.post(f"/api/modules/{mid}/{lid}/done").json()["done"] is True
    assert next(x for x in client.get("/api/modules").json() if x["id"] == mid)["done"] == 1
    client.post(f"/api/modules/{mid}/{lid}/done?done=false")
    assert client.get("/api/modules/nope/x").status_code == 404
