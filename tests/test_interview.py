import sqlite3

import pytest
from fastapi.testclient import TestClient

from drillpad.coach import interviewer as I
from drillpad.content.loader import load_all
from drillpad.core import db
from drillpad.web import interview as web_interview
from drillpad.web.app import create_app

CODE = "class DynamicArray:\n    def __init__(self):\n        self.a = []\n" + "    # pad\n" * 20


class StubLLM:
    """Records calls; classifier calls (haiku) answer from `label`, dialogue calls echo the directives."""

    def __init__(self, label="other"):
        self.calls, self.label = [], label

    def complete(self, *, model, system, messages, max_tokens):
        self.calls.append({"model": model, "system": system, "messages": messages})
        if model == I.CLASSIFIER_MODEL:
            return I.LLMReply(self.label, I.Usage(input_tokens=20, output_tokens=2))
        return I.LLMReply("Interviewer says: " + messages[-1]["content"].split("[directives]")[-1][:60],
                          I.Usage(input_tokens=100, output_tokens=20, cache_read_input_tokens=50))

    @property
    def dialogue(self):
        return [c for c in self.calls if c["model"] == I.DIALOGUE_MODEL]


@pytest.fixture
def conn():
    return db.connect(":memory:")


@pytest.fixture
def problem():
    return load_all()["dynamic-array"]


def start(problem, conn, fmt="timed-45", llm=None):
    llm = llm or StubLLM()
    iv, _ = I.Interviewer.start(problem, fmt, llm, I.InterviewStore(conn))
    return iv, llm


def test_interrupt_rules_fire_and_llm_only_phrases(problem, conn):
    iv, llm = start(problem, conn)
    assert iv.turn("", "", 2.0, 10).reply is None and not llm.calls      # nothing due: no LLM call
    r = iv.turn("", "", 5.0, 70)
    assert r.interjection == "silence" and r.reply
    assert "INTERRUPT (silence)" in llm.dialogue[-1]["messages"][-1]["content"]
    # cooldown: same rule is not repeated immediately
    assert iv.turn("", "", 6.0, 70).interjection is None
    assert iv.turn("", "", 9.5, 5).interjection == "no_approach"
    assert iv.turn("", "", 13.0, 5).interjection == "no_code"
    assert iv.turn("", CODE, 46.0, 0).interjection == "over"


def test_oa_has_no_interruptions_or_llm(problem, conn):
    iv, _ = I.Interviewer.start(problem, "oa", None, I.InterviewStore(conn))
    for m in (5, 20, 80):
        r = iv.turn("help, give me a hint", "", m, 300)
        assert r.reply is None and r.interjection is None and r.hint_level is None
    assert iv.hints_used == 0 and not I.FORMATS["oa"].voice


def test_hint_ladder_escalates_and_is_counted(problem, conn):
    iv, llm = start(problem, conn)
    levels = [iv.turn("I'm stuck, hint please", CODE, 10 + i, 0).hint_level for i in range(4)]
    assert levels == [1, 2, 3, 3]
    assert iv.hints_used == 4
    prompts = [c["messages"][-1]["content"] for c in llm.dialogue]
    assert "HINT level 1 (nudge)" in prompts[0]
    assert problem.hints[0] in prompts[1] and problem.hints[1] not in prompts[1]
    assert problem.hints[-1] in prompts[2]
    row = conn.execute("SELECT hints_used FROM interview_sessions WHERE id=?", (iv.sid,)).fetchone()
    assert row["hints_used"] == 4
    assert conn.execute("SELECT COUNT(*) FROM interview_events WHERE kind='hint'").fetchone()[0] == 4


def test_system_prefix_is_cached_and_static(problem, conn):
    iv, llm = start(problem, conn)
    iv.turn("what should happen on pop of empty?", CODE, 3, 0)
    iv.turn("and negative indexes?", CODE + "x", 4, 0)
    s1, s2 = (c["system"] for c in llm.dialogue)
    assert s1 == s2 and s1[-1]["cache_control"] == {"type": "ephemeral"}
    assert problem.hints[0] not in s1[-1]["text"] and problem.follow_ups[0] not in s1[-1]["text"]


def test_progressive_follow_up_timing(problem, conn):
    iv, _ = start(problem, conn, "progressive-60")
    assert iv.turn("", CODE, 14.0, 0).follow_up is None
    r = iv.turn("", CODE, 15.5, 0)                       # >=15 min and code exists
    assert r.follow_up == problem.follow_ups[0]
    assert iv.turn("", CODE, 20.0, 0).follow_up is None  # next only 15 min later
    assert iv.turn("", CODE, 31.0, 0).follow_up == problem.follow_ups[1]
    # no code yet: forced at the 20-minute maximum gap
    iv2, _ = start(problem, conn, "progressive-60")
    assert iv2.turn("", "", 19.0, 0).follow_up is None
    assert iv2.turn("", "", 20.0, 0).follow_up == problem.follow_ups[0]
    # timed-45 never injects
    iv3, _ = start(problem, conn, "timed-45")
    assert all(iv3.turn("", CODE, m, 0).follow_up is None for m in (15, 25, 35))


def test_finish_summary_and_persistence(problem, conn):
    iv, _ = start(problem, conn)
    iv.turn("My approach is a doubling array, amortized O(1) append", "", 6.0, 0)
    iv.turn("", CODE, 13.0, 0)
    iv.turn("hint?", CODE, 20.0, 0)
    s = iv.finish(True, 30.0)
    assert s["hints_used"] == 1 and s["ease"] == 2          # passed with a hint -> Hard
    assert s["first_approach_min"] == 6.0 and s["first_code_min"] == 13.0
    assert s["pace"][0]["phase"] == "clarify" and s["pace"][2]["turns"] >= 1
    assert s["usage"]["total"]["cache_read_input_tokens"] > 0 and s["usage"]["cost_is_estimate"]
    row = conn.execute("SELECT * FROM interview_sessions WHERE id=?", (iv.sid,)).fetchone()
    assert row["finished_at"] and row["est_cost_usd"] is not None
    roles = [e["role"] for e in conn.execute("SELECT role FROM interview_events WHERE session_id=?", (iv.sid,))]
    assert {"candidate", "interviewer", "system"} <= set(roles)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE interview_events SET content='x'")
    # restore from persisted events reproduces counters
    r = I.Interviewer.restore(problem, row, StubLLM(), I.InterviewStore(conn))
    assert r.hints_used == 1 and r.said_approach and len(r.transcript) == len(iv.transcript)


def test_haiku_classifier_sets_approach(problem, conn):
    iv, llm = start(problem, conn, llm=StubLLM(label="approach"))
    iv.turn("I'd keep a buffer and grow it when full", "", 8.0, 0)
    assert iv.said_approach and any(c["model"] == I.CLASSIFIER_MODEL for c in llm.calls)
    assert iv.turn("", "", 9.0, 0).interjection != "no_approach"


def test_missing_api_key_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import sys
    import types
    kr = types.ModuleType("keyring")
    kr.get_password = lambda *a: None
    monkeypatch.setitem(sys.modules, "keyring", kr)
    with pytest.raises(I.MissingAPIKeyError, match="ANTHROPIC_API_KEY"):
        I.AnthropicClient()


def test_key_from_env_or_keychain(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-env")
    assert I.resolve_api_key() == "sk-test-env"
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    import sys
    import types
    kr = types.ModuleType("keyring")
    kr.get_password = lambda svc, user: "sk-test-kc"
    monkeypatch.setitem(sys.modules, "keyring", kr)
    assert I.resolve_api_key() == "sk-test-kc"


def test_http_flow_and_no_secrets_in_db(tmp_path, monkeypatch):
    # publish-ok: fake value used to prove secrets are never stored
    secret = "sk-ant-SECRET-should-never-be-stored"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    stub = StubLLM()
    monkeypatch.setattr(web_interview, "default_llm_factory", lambda: stub)
    dbp = tmp_path / "t.db"
    c = TestClient(create_app(dbp))
    r = c.post("/api/interview/start", json={"problem_id": "dynamic-array", "format": "progressive-60"}).json()
    sid = r["session_id"]
    assert r["total_min"] == 60 and r["opening"]
    t = c.post(f"/api/interview/{sid}/turn", json={"message": "hint please", "code": CODE, "elapsed_min": 10}).json()
    assert t["hint_level"] == 1 and t["hints_used"] == 1 and t["reply"]
    f = c.post(f"/api/interview/{sid}/finish", json={"passed": False, "elapsed_min": 25}).json()
    assert f["ease"] == 1 and f["hints_used"] == 1
    assert c.post(f"/api/interview/{sid}/turn", json={"message": "x"}).status_code == 409
    assert c.post("/api/interview/start", json={"problem_id": "nope"}).status_code == 404
    assert c.post("/api/interview/start", json={"problem_id": "dynamic-array", "format": "zzz"}).status_code == 400
    assert secret.encode() not in dbp.read_bytes()


def test_http_start_without_key_is_clear_400(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import sys
    import types
    kr = types.ModuleType("keyring")
    kr.get_password = lambda *a: None
    monkeypatch.setitem(sys.modules, "keyring", kr)
    c = TestClient(create_app(tmp_path / "t.db"))
    r = c.post("/api/interview/start", json={"problem_id": "dynamic-array"})
    assert r.status_code == 400 and "ANTHROPIC_API_KEY" in r.json()["detail"]
    # OA needs no key
    assert c.post("/api/interview/start", json={"problem_id": "dynamic-array", "format": "oa"}).status_code == 200
