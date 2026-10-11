"""Study planner API: knobs in, today's queue out (with reasons)."""

import dataclasses
import logging
import os
import time
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from drillpad.anki.ankiconnect import AnkiConnect
from drillpad.evaluation.firms import load_profiles
from drillpad.evaluation.progress import _rows
from drillpad.planner import engine
from drillpad.planner import settings as st
from drillpad.srs import engine as srs

_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"
_anki_cache: dict = {"t": 0.0, "ids": set(), "ok": None}


class PresetRequest(BaseModel):
    id: str


def _ts(s: str) -> datetime:
    return datetime.strptime(s, _FMT).replace(tzinfo=UTC)


def make_router(problems: dict, conn) -> APIRouter:
    router = APIRouter(prefix="/api/plan")
    profiles = load_profiles()

    def anki_due_ids() -> tuple[set[str], bool | None]:
        """Best effort, cached 60s, never blocks the page on Anki being closed."""
        if time.time() - _anki_cache["t"] < 60:
            return _anki_cache["ids"], _anki_cache["ok"]
        ids, ok = set(), False
        try:
            a = AnkiConnect(url=os.environ.get("DRILLPAD_ANKI_URL", "http://127.0.0.1:8765"),
                            client=httpx.Client(timeout=1.5))
            q = {p.id: p.anki_queries for p in problems.values() if p.anki_queries}
            ids = {c.problem_id for c in a.due(q)}
            ok = True
        except Exception as e:  # noqa: BLE001 - Anki closed/unreachable is normal
            logging.getLogger(__name__).info("Anki unavailable for plan: %s", e)
        _anki_cache.update(t=time.time(), ids=ids, ok=ok)
        return ids, ok

    def context(minutes: int | None = None, use_anki: bool = True) -> dict:
        s = st.load(conn)
        evals = _rows(conn)
        latest = {e["problem_id"]: e for e in evals}
        miss: dict[str, list[int]] = {}
        for e in evals:
            for tag, (first, _final, total) in e["fr"].detail.get("edge_by_tag", {}).items():
                m = miss.setdefault(tag, [0, 0])
                m[0] += total - first
                m[1] += total
        edge_miss = {t: a / n for t, (a, n) in miss.items() if n}
        last_attempt = {r["problem_id"]: _ts(r["t"]) for r in conn.execute(
            "SELECT problem_id, MAX(started_at) t FROM attempts GROUP BY problem_id")}
        now = datetime.now(UTC)
        forced = {}
        for r in conn.execute(
            """SELECT a.problem_id pid, MAX(v.created_at) t FROM solution_views v JOIN attempts a ON a.id = v.attempt_id
               WHERE v.reason = 'stuck' GROUP BY a.problem_id"""):
            age = (now - _ts(r["t"])).total_seconds() / 86400
            if age <= 3:
                done = conn.execute(
                    """SELECT 1 FROM attempts a JOIN revisions rv ON rv.attempt_id = a.id AND rv.passed = 1
                       WHERE a.problem_id = ? AND a.mode = 'recall' AND a.started_at > ?""", (r["pid"], r["t"])).fetchone()
                if not done:
                    forced[r["pid"]] = int(age)
        due, anki_ok = anki_due_ids() if (use_anki and s.use_anki) else (set(), None)
        out = engine.build(s, problems, profiles, latest, last_attempt, edge_miss, due, forced, now, minutes,
                           srs_snapshot=srs.snapshot(conn, now))
        out["settings"] = dataclasses.asdict(s)
        out["anki"] = {"connected": anki_ok, "due": sorted(due)}
        return out

    @router.get("")
    def plan(minutes: int | None = None):
        out = context(minutes)
        out["presets"] = {k: v["label"] for k, v in st.PRESETS.items()}
        out["category_labels"] = st.CATEGORY_LABELS
        out["language_labels"] = st.LANGUAGE_LABELS
        out["firm_options"] = [{"id": p.id, "name": p.name, "family": p.family} for p in profiles.values()
                               if p.id != "generic" and not p.id.startswith("generic-")]
        return out

    @router.put("/settings")
    def put_settings(body: dict):
        s = st.from_dict(body)
        unknown = [f.id for f in s.firms if f.id not in profiles]
        if unknown:
            raise HTTPException(400, f"unknown firm id(s): {unknown}")
        st.save(conn, s)
        return plan()

    @router.post("/preset")
    def preset(req: PresetRequest):
        if req.id not in st.PRESETS:
            raise HTTPException(404, "unknown preset")
        st.save(conn, st.apply_preset(st.load(conn), req.id))
        return plan()

    return router
