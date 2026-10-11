"""Evaluation + progress API."""

import dataclasses
import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from drillpad.anki.ankiconnect import AnkiConnect, AnkiConnectError
from drillpad.anki.scheduler import ease_for
from drillpad.core import db
from drillpad.evaluation import engine, progress
from drillpad.evaluation.firms import load_profiles
from drillpad.runner import registry
from drillpad.srs import engine as srs

SOLUTIONS = Path(__file__).resolve().parent.parent / "content" / "solutions"


class SolutionRequest(BaseModel):
    reason: str  # 'passed' | 'stuck'


class AnkiRequest(BaseModel):
    ease: int | None = None  # override the suggested rating (1-4)


class EvalRequest(BaseModel):
    firm_id: str = "generic"
    complexity: dict[str, dict[str, str]] = {}
    extensions: list[dict] = []  # [{idx, answer, covered: [bool,...]}]
    communication: dict | None = None


def make_router(problems: dict, conn) -> APIRouter:
    router = APIRouter(prefix="/api")
    profiles = load_profiles()

    @router.get("/firms")
    def firms():
        return [{"id": p.id, "name": p.name, "family": p.family, "pass_score": p.pass_score, "weights": p.weights,
                 "floors": p.floors, "earns": p.earns, "loses": p.loses, "red_flags": p.red_flags,
                 "problem_ids": p.problem_ids, "missing_problems": p.missing_problems, "tags": p.tags,
                "format_confidence": p.format_confidence, "rubric_confidence": p.rubric_confidence}
                for p in profiles.values()]

    @router.get("/attempts/{aid}/extensions/{idx}/key_points")
    def reveal(aid: int, idx: int):
        row = conn.execute("SELECT problem_id FROM attempts WHERE id = ?", (aid,)).fetchone()
        if not row:
            raise HTTPException(404, "unknown attempt")
        exts = problems[row["problem_id"]].extensions
        if not 0 <= idx < len(exts):
            raise HTTPException(404, "unknown extension")
        return {"key_points": exts[idx].key_points}

    @router.post("/attempts/{aid}/evaluate")
    def evaluate(aid: int, req: EvalRequest):
        row = conn.execute("SELECT problem_id, started_at FROM attempts WHERE id = ?", (aid,)).fetchone()
        if not row:
            raise HTTPException(404, "unknown attempt")
        profile = profiles.get(req.firm_id) or profiles["generic"]
        problem = problems[row["problem_id"]]
        stuck = conn.execute(
            "SELECT MIN(created_at) t FROM solution_views WHERE attempt_id = ? AND reason = 'stuck'", (aid,)
        ).fetchone()["t"]
        revs = [r for r in db.revisions(conn, aid) if not stuck or r["created_at"] < stuck]
        fr = engine.raw_fractions(problem, revs, row["started_at"], profile,
                                  req.complexity, req.extensions, req.communication, gave_up=bool(stuck))
        score = engine.apply_profile(fr, profile)
        engine.store_evaluation(conn, aid, problem.id, fr, {
            "complexity": req.complexity, "extensions": req.extensions, "communication": req.communication,
            "firm_id": profile.id})
        return {"score": dataclasses.asdict(score), "detail": fr.detail, "dims": fr.dims}

    @router.post("/attempts/{aid}/solution")
    def solution(aid: int, req: SolutionRequest):
        row = conn.execute("SELECT problem_id FROM attempts WHERE id = ?", (aid,)).fetchone()
        if not row:
            raise HTTPException(404, "unknown attempt")
        if req.reason not in ("passed", "stuck"):
            raise HTTPException(400, "reason must be 'passed' or 'stuck'")
        p = problems[row["problem_id"]]
        if req.reason == "passed" and not conn.execute(
                "SELECT 1 FROM revisions WHERE attempt_id = ? AND passed = 1", (aid,)).fetchone():
            raise HTTPException(409, "No passing run on this attempt yet. Pass first, or declare yourself stuck.")
        f = SOLUTIONS / f"{p.id}{registry.EXT.get(p.language, '.py')}"
        if not f.exists():
            raise HTTPException(404, "no reference solution for this problem")
        conn.execute("INSERT INTO solution_views(attempt_id, reason) VALUES (?, ?)", (aid, req.reason))
        conn.commit()
        if req.reason == "stuck":
            srs.review(conn, p.id, aid, 1, "stuck")  # gave up = Again
        code = "\n".join(line for line in f.read_text().splitlines() if not line.startswith("# ruff: noqa")
                         and not line.startswith("# Reference solution copied")).strip() + "\n"
        # solutions are shown as written; only python files carry lint/comment headers
        return {"solution": code, "walkthrough": p.walkthrough, "narration": p.narration,
                "state_aloud": p.state_aloud, "gave_up": req.reason == "stuck",
                "complexity": [dataclasses.asdict(c) for c in p.complexity]}

    def _suggest(aid: int) -> dict:
        row = conn.execute("SELECT problem_id, started_at FROM attempts WHERE id = ?", (aid,)).fetchone()
        if not row:
            raise HTTPException(404, "unknown attempt")
        p = problems[row["problem_id"]]
        stuck = conn.execute("SELECT 1 FROM solution_views WHERE attempt_id = ? AND reason = 'stuck'", (aid,)).fetchone()
        revs = db.revisions(conn, aid)
        solved = next((r for r in revs if r["passed"]), None)
        if stuck or not solved:
            return {"ease": 1, "label": "Again", "why": "gave up" if stuck else "not solved", "problem": p}
        mins = engine.solve_minutes(solved, row["started_at"]) * 60
        ease = ease_for(True, 0, mins / 60, p.target_minutes)
        return {"ease": ease, "label": ["", "Again", "Hard", "Good", "Easy"][ease],
                "why": f"solved in {mins / 60:.1f} min vs {p.target_minutes} min target", "problem": p}

    @router.get("/attempts/{aid}/anki")
    def anki_suggest(aid: int):
        s = _suggest(aid)
        return {k: v for k, v in s.items() if k != "problem"} | {"queries": s["problem"].anki_queries}

    @router.post("/attempts/{aid}/anki")
    def anki_send(aid: int, req: AnkiRequest):
        s = _suggest(aid)
        ease = req.ease or s["ease"]
        if ease not in (1, 2, 3, 4):
            raise HTTPException(400, "ease must be 1-4")
        p = s["problem"]
        if not p.anki_queries:
            raise HTTPException(404, "this problem is not linked to an Anki card")
        try:
            anki = AnkiConnect(url=os.environ.get("DRILLPAD_ANKI_URL", "http://127.0.0.1:8765"))
            cards = anki.due({p.id: p.anki_queries}, include_new=True)
            for c in cards:
                anki.answer(c.card_id, ease)
        except AnkiConnectError as e:
            raise HTTPException(503, f"Anki not reachable: {e}") from e
        if not cards:
            return {"sent": 0, "message": "No due or new card for this problem; scheduling left untouched."}
        return {"sent": len(cards), "ease": ease, "message": f"Rated {len(cards)} card(s) {['', 'Again', 'Hard', 'Good', 'Easy'][ease]} in Anki."}

    @router.get("/progress")
    def prog(firm: str = "generic"):
        return progress.build(conn, problems, profiles, firm)

    return router


__all__ = ["json", "make_router"]
