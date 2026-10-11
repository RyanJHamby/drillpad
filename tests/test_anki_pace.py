import httpx

from drillpad.anki.ankiconnect import AnkiConnect, AnkiConnectError
from drillpad.anki.scheduler import ease_for
from drillpad.coach.pace import check, phase_at


def fake_anki(calls):
    def handler(req):
        import json
        b = json.loads(req.content)
        calls.append((b["action"], b["params"]))
        res = {"findCards": [1, 2] if "Item:1" in b["params"].get("query", "") else [], "answerCards": [True]}.get(b["action"])
        return httpx.Response(200, json={"result": res, "error": None})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_due_uses_problem_queries_only():
    calls = []
    a = AnkiConnect(client=fake_anki(calls))
    due = a.due({"dynamic-array": ['deck:"Interview Prep*" "Item:1 - *"'], "other": ['"Item:9 - *"']})
    assert [(c.card_id, c.problem_id) for c in due] == [(1, "dynamic-array"), (2, "dynamic-array")]
    assert calls[0][1]["query"].endswith("is:due")
    a.answer(1, 3)
    assert calls[-1][0] == "answerCards"


def test_unreachable_raises():
    def boom(req):
        raise httpx.ConnectError("down")
    a = AnkiConnect(client=httpx.Client(transport=httpx.MockTransport(boom)))
    try:
        a.due({"p": ["q"]})
    except AnkiConnectError:
        return
    raise AssertionError


def test_ease_mapping():
    assert ease_for(False, 0, 5, 20) == 1
    assert ease_for(True, 1, 5, 20) == 2
    assert ease_for(True, 0, 25, 20) == 2
    assert ease_for(True, 0, 15, 20) == 3
    assert ease_for(True, 0, 10, 20) == 4


def test_pace_rules():
    assert phase_at(3) == "clarify" and phase_at(20) == "code" and phase_at(46) == "over"
    assert check(2, 10, 0, False) is None
    assert check(5, 70, 0, False).kind == "silence"
    assert check(8, 5, 0, False).kind == "no_approach"
    assert check(13, 5, 0, True).kind == "no_code"
    assert check(31, 5, 20, True).kind == "behind"
    assert check(46, 0, 500, True).kind == "over"
