import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from drillpad.coach import weakness as wk
from drillpad.content.loader import load_all
from drillpad.core import db
from drillpad.core.models import Problem

NOW = datetime(2026, 10, 6, tzinfo=UTC)


def iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def prob(pid, patterns):
    return Problem(id=pid, title=pid, statement="", starter="", tests=[], patterns=patterns)


@pytest.fixture
def conn():
    return db.connect(":memory:")


def finished_attempt(conn, pid, days_ago, outcome="failed"):
    cur = conn.execute(
        "INSERT INTO attempts(problem_id, mode, started_at, finished_at, outcome) VALUES (?,?,?,?,?)",
        (pid, "timed", iso(days_ago), iso(days_ago), outcome),
    )
    conn.commit()
    return cur.lastrowid


def test_migration_idempotent_and_existing_tables_untouched():
    c = sqlite3.connect(":memory:")
    c.executescript(db.SCHEMA)
    db.migrate_add_weakness_events(c)
    db.migrate_add_weakness_events(c)
    names = {r[0] for r in c.execute("select name from sqlite_master")}
    assert {"attempts", "revisions", "weakness_events", "revisions_no_update"} <= names
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("insert into attempts(problem_id, mode) values ('p','m')")
        c.execute("insert into weakness_events(attempt_id, category, tag, severity) values (1,'pattern','x',9)")


def test_decay_half_life():
    assert wk.decay(14, 14) == pytest.approx(0.5)
    assert wk.decay(28, 14) == pytest.approx(0.25)
    assert wk.decay(7, 7) == pytest.approx(0.5)  # configurable


def test_recent_failures_outrank_old(conn):
    probs = {"a": prob("a", ["bfs"]), "b": prob("b", ["trie"])}
    for pid, age in (("a", 1), ("b", 60)):
        att = finished_attempt(conn, pid, age)
        wk.record_event(conn, att, "pattern", probs[pid].patterns[0], 3, created_at=iso(age))
    scores = wk.weakness_scores(conn, probs, NOW)
    ranked = wk.rank_tags(scores)
    assert [s.tag for s in ranked] == ["bfs", "trie"]
    assert ranked[0].score > 4 * ranked[1].score


def test_failure_rate_uses_successes_as_exposure(conn):
    probs = {"a": prob("a", ["bfs"])}
    bad = finished_attempt(conn, "a", 1)
    wk.record_event(conn, bad, "pattern", "bfs", 3, created_at=iso(1))
    s1 = wk.weakness_scores(conn, probs, NOW)[("pattern", "bfs")].score
    for _ in range(4):
        finished_attempt(conn, "a", 1, "passed")
    s2 = wk.weakness_scores(conn, probs, NOW)[("pattern", "bfs")].score
    assert s2 < s1


def test_one_event_per_attempt_tag_takes_max_severity(conn):
    probs = {"a": prob("a", ["bfs"])}
    att = finished_attempt(conn, "a", 0)
    wk.record_event(conn, att, "pattern", "bfs", 1, created_at=iso(0))
    wk.record_event(conn, att, "pattern", "bfs", 3, created_at=iso(0))
    s = wk.weakness_scores(conn, probs, NOW)[("pattern", "bfs")]
    assert s.failure_weight == pytest.approx(1.0)


def test_non_pattern_category_exposure_is_all_attempts(conn):
    probs = {"a": prob("a", []), "b": prob("b", [])}
    a1 = finished_attempt(conn, "a", 0)
    finished_attempt(conn, "b", 0, "passed")
    wk.record_event(conn, a1, "communication", "silence-while-thinking", 3, created_at=iso(0))
    s = wk.weakness_scores(conn, probs, NOW)[("communication", "silence-while-thinking")]
    assert s.exposure_weight == pytest.approx(2.0)
    assert s.score == pytest.approx(1.0 / 3.0)


def test_record_event_validates(conn):
    att = db.start_attempt(conn, "a")
    with pytest.raises(ValueError):
        wk.record_event(conn, att, "vibes", "x")
    with pytest.raises(sqlite3.IntegrityError):
        wk.record_event(conn, att, "pattern", "x", severity=0)


def test_boost_and_queue(conn):
    probs = {"weak": prob("weak", ["bfs", "trie"]), "fine": prob("fine", ["heap-top-k"]), "none": prob("none", [])}
    att = finished_attempt(conn, "weak", 0)
    wk.record_event(conn, att, "pattern", "bfs", 3, created_at=iso(0))
    scores = wk.weakness_scores(conn, probs, NOW)
    cfg = wk.WeaknessConfig(max_boost=1.0)
    assert wk.problem_boost(probs["fine"], scores, cfg) == 1.0
    assert wk.problem_boost(probs["none"], scores, cfg) == 1.0
    assert wk.problem_boost(probs["weak"], scores, cfg) > 1.0
    q = wk.boost_queue({"fine": 1.0, "weak": 0.8, "ghost": 0.5}, probs, scores, cfg)
    assert q[0][0] == "weak" and dict(q)["ghost"] == 0.5


def test_seeds_load_and_are_unconfirmed():
    seeds = wk.load_seeds()
    assert {s.category for s in seeds} == set(wk.CATEGORIES)
    assert all(s.status == "user-to-confirm" and s.source and not s.confirmed for s in seeds)
    assert all(s.evidence in ("recorded", "drill-prescribed") for s in seeds)


def test_unconfirmed_seeds_ignored_confirmed_seeds_count(conn):
    probs = load_all()
    seeds = wk.load_seeds()
    assert wk.weakness_scores(conn, probs, NOW, seeds=seeds) == {}
    from dataclasses import replace
    confirmed = [replace(s, status="confirmed") if s.tag == "cpp-fluency" else s for s in seeds]
    sc = wk.weakness_scores(conn, probs, NOW, seeds=confirmed)
    assert list(sc) == [("language", "cpp-fluency")] and sc[("language", "cpp-fluency")].score > 0
