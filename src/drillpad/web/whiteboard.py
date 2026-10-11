"""Whiteboard practice log: self-scored (1-5) sessions per lesson, scheduled with FSRS.

Only the sessions are stored. A lesson's card is rebuilt by replaying its sessions in time order, so
deleting a mistaken entry or backfilling an older one always yields a consistent schedule. Scores map to
FSRS ratings as: 1 Again, 2-3 Hard (not yet solid), 4 Good, 5 Easy. The raw 1-5 score is kept for display.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from fsrs import Card, Rating, Scheduler
from pydantic import BaseModel, Field

from drillpad.web.modules import _load

DESIRED_RETENTION = 0.95  # higher than the default 0.9: interview prep is time-boxed, so review more often
MAX_INTERVAL_DAYS = 45
# No learning steps: a whiteboard session is a long exercise, so reviews graduate straight to day-scale
# intervals. Fuzzing off so replaying the same sessions always gives the same due date.
_SCHED = Scheduler(desired_retention=DESIRED_RETENTION, learning_steps=(), relearning_steps=(), enable_fuzzing=False,
                   maximum_interval=MAX_INTERVAL_DAYS)
_RATINGS = {1: Rating.Again, 2: Rating.Hard, 3: Rating.Hard, 4: Rating.Good, 5: Rating.Easy}


class SessionIn(BaseModel):
    score: int = Field(ge=1, le=5)
    notes: str = Field(default="", max_length=2000)
    at: str | None = None  # ISO timestamp or date, for backfilling a session that already happened


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _state(rows: list, now: datetime) -> dict:
    """Schedule state for one lesson from its sessions (oldest first)."""
    card = Card()
    for r in rows:
        card, _ = _SCHED.review_card(card, _RATINGS[r["score"]], _parse(r["created_at"]))
    last = rows[-1]
    recent = [r["score"] for r in rows[-3:]]
    return {
        "sessions": len(rows), "last_score": last["score"], "last_at": last["created_at"],
        "recent_avg": round(sum(recent) / len(recent), 2),
        "due": card.due.isoformat(), "due_now": card.due <= now,
        "retrievability": round(_SCHED.get_card_retrievability(card, now), 3),
    }


def make_router(problems: dict, conn) -> APIRouter:
    router = APIRouter(prefix="/api/whiteboard")

    def lesson_rows(mid: str, lid: str) -> list:
        return conn.execute("SELECT id, score, notes, created_at FROM whiteboard_sessions WHERE module_id = ? AND lesson_id = ? "
                            "ORDER BY created_at, id", (mid, lid)).fetchall()

    def check(mid: str, lid: str) -> None:
        mods = _load()
        if mid not in mods or lid not in {x["id"] for x in mods[mid]["lessons"]}:
            raise HTTPException(404, "unknown lesson")

    def detail(mid: str, lid: str) -> dict:
        rows = lesson_rows(mid, lid)
        history = [{"id": r["id"], "score": r["score"], "notes": r["notes"], "at": r["created_at"]} for r in rows]
        state = _state(rows, datetime.now(UTC)) if rows else None
        return {"module": mid, "lesson": lid, "state": state, "history": list(reversed(history))}

    @router.get("")
    def overview():
        """Every whiteboarded lesson with its schedule, plus the due queue (most overdue first)."""
        now = datetime.now(UTC)
        mods = _load()
        by_lesson: dict[tuple[str, str], list] = {}
        for r in conn.execute("SELECT module_id, lesson_id, id, score, notes, created_at FROM whiteboard_sessions "
                              "ORDER BY created_at, id"):
            by_lesson.setdefault((r["module_id"], r["lesson_id"]), []).append(r)
        lessons, due = {}, []
        for (mid, lid), rows in by_lesson.items():
            if mid not in mods:
                continue  # lesson/module removed from the curriculum: keep the log, hide it here
            title = next((x["title"] for x in mods[mid]["lessons"] if x["id"] == lid), lid)
            st = _state(rows, now)
            lessons[f"{mid}/{lid}"] = st
            if st["due_now"]:
                due.append({"module": mid, "lesson": lid, "module_title": mods[mid]["title"], "title": title, **st})
        due.sort(key=lambda x: x["due"])
        total = sum(len(m["lessons"]) for m in mods.values())
        return {"lessons": lessons, "due": due,
                "summary": {"total_lessons": total, "whiteboarded": len(lessons), "due_now": len(due),
                            "mean_last_score": round(sum(v["last_score"] for v in lessons.values()) / len(lessons), 2)
                            if lessons else None}}

    @router.get("/{mid}/{lid}")
    def lesson(mid: str, lid: str):
        check(mid, lid)
        return detail(mid, lid)

    @router.post("/{mid}/{lid}")
    def log(mid: str, lid: str, body: SessionIn):
        check(mid, lid)
        now = datetime.now(UTC)
        when = now
        if body.at:
            try:
                when = _parse(body.at)
            except ValueError:
                raise HTTPException(422, "at must be an ISO date or timestamp") from None
            if when > now + timedelta(minutes=5):
                raise HTTPException(422, "at cannot be in the future")
        conn.execute("INSERT INTO whiteboard_sessions(module_id, lesson_id, score, notes, created_at) VALUES (?,?,?,?,?)",
                     (mid, lid, body.score, body.notes.strip(), when.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"))
        conn.commit()
        return detail(mid, lid)

    @router.delete("/sessions/{sid}")
    def delete(sid: int):
        row = conn.execute("SELECT module_id, lesson_id FROM whiteboard_sessions WHERE id = ?", (sid,)).fetchone()
        if not row:
            raise HTTPException(404, "unknown session")
        conn.execute("DELETE FROM whiteboard_sessions WHERE id = ?", (sid,))
        conn.commit()
        return detail(row["module_id"], row["lesson_id"])

    return router
