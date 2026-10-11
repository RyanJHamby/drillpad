"""Spaced repetition for DrillPad's own problems (FSRS via py-fsrs).

A review is logged once per attempt: the first passing run (rating from time vs target) or opening the
solution while stuck (Again). Retrievability (estimated recall probability) feeds the planner and the
Questions page. Anki remains separate: this covers problems that have no Anki card.
"""

import json
from datetime import UTC, datetime

from fsrs import Card, Rating, Scheduler

DESIRED_RETENTION = 0.9
_SCHED = Scheduler(desired_retention=DESIRED_RETENTION)
_RATINGS = {1: Rating.Again, 2: Rating.Hard, 3: Rating.Good, 4: Rating.Easy}


def review(conn, problem_id: str, attempt_id: int, ease: int, source: str, now: datetime | None = None) -> bool:
    """Log one review for this attempt. Returns False if the attempt was already counted."""
    now = now or datetime.now(UTC)
    with conn.lock:
        if conn.execute("SELECT 1 FROM srs_reviews WHERE attempt_id = ?", (attempt_id,)).fetchone():
            return False
        row = conn.execute("SELECT card_json FROM srs_cards WHERE problem_id = ?", (problem_id,)).fetchone()
        card = Card.from_json(row["card_json"]) if row else Card()
        card, _log = _SCHED.review_card(card, _RATINGS[ease], now)
        conn.execute(
            "INSERT INTO srs_cards(problem_id, card_json) VALUES (?, ?) ON CONFLICT(problem_id) DO UPDATE SET "
            "card_json = excluded.card_json, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')",
            (problem_id, card.to_json()))
        conn.execute("INSERT INTO srs_reviews(problem_id, attempt_id, ease, source) VALUES (?,?,?,?)",
                     (problem_id, attempt_id, ease, source))
        conn.commit()
    return True


def snapshot(conn, now: datetime | None = None) -> dict[str, dict]:
    """Per reviewed problem: current recall estimate, next due time, review count."""
    now = now or datetime.now(UTC)
    counts = {r["problem_id"]: r["n"] for r in conn.execute(
        "SELECT problem_id, COUNT(*) n FROM srs_reviews GROUP BY problem_id")}
    out = {}
    for r in conn.execute("SELECT problem_id, card_json FROM srs_cards"):
        card = Card.from_dict(json.loads(r["card_json"]))
        rec = _SCHED.get_card_retrievability(card, now)
        out[r["problem_id"]] = {
            "retrievability": round(rec, 3), "due": card.due.isoformat(), "stability_days": round(card.stability or 0, 2),
            "reviews": counts.get(r["problem_id"], 0), "due_now": rec < DESIRED_RETENTION,
            "days_since": round((now - card.last_review).total_seconds() / 86400, 1) if card.last_review else None,
        }
    return out
