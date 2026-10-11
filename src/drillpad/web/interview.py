"""Interview-mode HTTP API. Mounted by web.app.create_app via make_router(problems, conn)."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from drillpad.coach import interviewer as iv_mod
from drillpad.coach.interviewer import (
    FORMATS,
    Interviewer,
    InterviewStore,
    MissingAPIKeyError,
)
from drillpad.coach.pace import PHASES_45


def default_llm_factory():
    """Looked up at call time so tests can monkeypatch it."""
    return iv_mod.AnthropicClient()


class StartRequest(BaseModel):
    problem_id: str
    format: str = "timed-45"


class TurnRequest(BaseModel):
    message: str = ""
    code: str = ""
    elapsed_min: float | None = None     # client clock; server clock used if omitted
    silence_s: float = 0.0


class FinishRequest(BaseModel):
    passed: bool = False
    elapsed_min: float | None = None


def make_router(problems: dict, conn) -> APIRouter:
    router = APIRouter(prefix="/api/interview")
    store = InterviewStore(conn)
    live: dict[int, Interviewer] = {}
    started: dict[int, float] = {}

    def llm_for(fmt_name: str):
        if not FORMATS[fmt_name].chat:
            return None
        return default_llm_factory()

    def get(sid: int) -> Interviewer:
        if sid in live:
            return live[sid]
        row = store.session(sid)
        if not row:
            raise HTTPException(404, "unknown interview session")
        if row["finished_at"]:
            raise HTTPException(409, "interview already finished")
        try:
            iv = Interviewer.restore(problems[row["problem_id"]], row, llm_for(row["format"]), store)
        except MissingAPIKeyError as e:
            raise HTTPException(400, str(e)) from e
        live[sid] = iv
        started.setdefault(sid, time.monotonic())
        return iv

    def elapsed(sid: int, given: float | None) -> float:
        return given if given is not None else (time.monotonic() - started.get(sid, time.monotonic())) / 60

    @router.get("/formats")
    def formats():
        return {n: {"total_min": f.total_min, "chat": f.chat, "interrupts": f.interrupts, "voice": f.voice}
                for n, f in FORMATS.items()}

    @router.post("/start")
    def start(req: StartRequest):
        if req.problem_id not in problems:
            raise HTTPException(404, "unknown problem")
        if req.format not in FORMATS:
            raise HTTPException(400, f"unknown format; choose from {sorted(FORMATS)}")
        try:
            llm = llm_for(req.format)
        except MissingAPIKeyError as e:
            raise HTTPException(400, str(e)) from e
        iv, opening = Interviewer.start(problems[req.problem_id], req.format, llm, store)
        live[iv.sid] = iv
        started[iv.sid] = time.monotonic()
        f = iv.fmt
        return {"session_id": iv.sid, "opening": opening, "format": f.name, "total_min": f.total_min,
                "chat": f.chat, "phases": [{"name": n, "start": s * f.total_min / 45, "end": e * f.total_min / 45}
                                           for n, s, e in PHASES_45]}

    @router.post("/{sid}/turn")
    def turn(sid: int, req: TurnRequest):
        iv = get(sid)
        try:
            r = iv.turn(req.message, req.code, elapsed(sid, req.elapsed_min), req.silence_s)
        except MissingAPIKeyError as e:
            raise HTTPException(400, str(e)) from e
        return {"reply": r.reply, "phase": r.phase, "elapsed_min": r.elapsed_min, "interjection": r.interjection,
                "hint_level": r.hint_level, "follow_up": r.follow_up, "hints_used": r.hints_used}

    @router.post("/{sid}/finish")
    def finish(sid: int, req: FinishRequest):
        iv = get(sid)
        summary = iv.finish(req.passed, elapsed(sid, req.elapsed_min))
        live.pop(sid, None)
        return summary

    return router
