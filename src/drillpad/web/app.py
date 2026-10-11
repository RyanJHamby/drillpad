import dataclasses
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from drillpad.anki.scheduler import ease_for
from drillpad.content.loader import load_all
from drillpad.core import db, paths
from drillpad.evaluation.engine import _ts, solve_minutes
from drillpad.readiness.model import load_config
from drillpad.readiness.progress import level_progress, solves_by_problem
from drillpad.runner import registry
from drillpad.srs import engine as srs
from drillpad.web.backup import backup_database
from drillpad.web.eval import make_router as make_eval_router
from drillpad.web.interview import make_router
from drillpad.web.modules import make_router as make_modules_router
from drillpad.web.plan import make_router as make_plan_router
from drillpad.web.questions import make_router as make_questions_router
from drillpad.web.whiteboard import make_router as make_whiteboard_router

STATIC = Path(__file__).parent / "static"
DRILLPAD_DIR = Path(__file__).parent.parent
ROOT_DIR = DRILLPAD_DIR.parent.parent


class RunRequest(BaseModel):
    code: str
    active_ms: int | None = None  # client's un-paused time on this attempt


class ScratchRequest(BaseModel):
    code: str
    stdin: str = ""
    problem_id: str | None = None  # supplies the problem's helper prelude (TreeNode, builders, ...)


class AttemptRequest(BaseModel):
    problem_id: str
    mode: str = "practice"


class DraftRequest(BaseModel):
    code: str
    attempt_id: int | None = None
    active_ms: int | None = None


def _clamp_active(conn, aid: int, active_ms: int | None) -> int | None:
    """Client-reported active time, bounded by the wall-clock age of the attempt (it can only be <= that)."""
    if active_ms is None:
        return None
    row = conn.execute("SELECT started_at FROM attempts WHERE id = ?", (aid,)).fetchone()
    wall_ms = int((datetime.now(UTC) - _ts(row["started_at"])).total_seconds() * 1000) if row else active_ms
    return max(0, min(int(active_ms), wall_ms + 2000))


def _save_clock(conn, aid: int, active_ms: int | None) -> None:
    if active_ms is None:
        return
    conn.execute(
        "INSERT INTO attempt_clock(attempt_id, active_ms) VALUES (?, ?) ON CONFLICT(attempt_id) DO UPDATE SET "
        "active_ms = MAX(active_ms, excluded.active_ms), updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')", (aid, active_ms))
    conn.commit()


def create_app(db_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="DrillPad")

    @app.middleware("http")
    async def no_cache(request, call_next):
        resp = await call_next(request)
        if not request.url.path.startswith("/api"):
            resp.headers["Cache-Control"] = "no-store"  # local tool: never serve a stale UI
        return resp

    problems = load_all()
    if db_path:
        db_file = Path(db_path)
    else:
        db_file = paths.db_path()
        paths.migrate_legacy_db(db_file)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = db.connect(db_file, check_same_thread=False)

    backup_database(db_file)  # consistent local snapshot on every start; cli.serve adds a periodic one

    def visible(p):
        d = dataclasses.asdict(p)
        d["tests"] = [t for t in d["tests"] if not t["hidden"]]
        d["complexity_ops"] = [c["op"] for c in d.pop("complexity")]
        d["extensions"] = [{"q": e["q"], "kind": e["kind"], "points": len(e["key_points"])} for e in d["extensions"]]
        return d

    cfg = load_config()

    @app.get("/api/problems")
    def list_problems():
        solves = solves_by_problem(conn, problems)
        return [
            {"id": p.id, "title": p.title, "bar_level": p.bar_level, "patterns": p.patterns,
             "firm_tags": p.firm_tags, "target_minutes": p.target_minutes, "language": p.language,
             "solved": bool(solves.get(p.id)), "best_minutes": round(min((s.elapsed_min for s in solves.get(p.id, [])), default=0), 1) or None}
            for p in sorted(problems.values(), key=lambda p: (p.bar_level, p.title))
        ]

    @app.get("/api/readiness")
    def readiness():
        levels = level_progress(cfg, problems, solves_by_problem(conn, problems))
        weighted = [(lv["readiness"], lv["problems"]) for lv in levels if lv["problems"]]
        total = sum(n for _, n in weighted)
        overall = sum(r * n for r, n in weighted) / total if total else 0.0
        return {"overall": round(overall, 3), "levels": levels,
                "note": "Initial heuristic thresholds; scored per problem at each bar level."}

    @app.get("/api/problems/{pid}")
    def get_problem(pid: str):
        if pid not in problems:
            raise HTTPException(404, "unknown problem")
        return visible(problems[pid])

    @app.get("/api/problems/{pid}/attempts")
    def problem_attempts(pid: str):
        """Past attempts for a problem (only ones with at least one run), newest first."""
        if pid not in problems:
            raise HTTPException(404, "unknown problem")
        rows = conn.execute(
            """SELECT a.id, a.mode, a.started_at, COUNT(r.id) AS runs, COALESCE(MAX(r.passed), 0) AS passed,
                      MIN(CASE WHEN r.passed = 1 THEN r.id END) AS first_pass_rev
               FROM attempts a JOIN revisions r ON r.attempt_id = a.id
               WHERE a.problem_id = ? GROUP BY a.id ORDER BY a.id DESC LIMIT 50""", (pid,)).fetchall()
        out = []
        for r in rows:
            mins = None
            if r["first_pass_rev"] is not None:
                rev = conn.execute("SELECT created_at, active_ms FROM revisions WHERE id = ?", (r["first_pass_rev"],)).fetchone()
                mins = round(solve_minutes(rev, r["started_at"]), 1)
            out.append({"id": r["id"], "mode": r["mode"], "started_at": r["started_at"], "runs": r["runs"],
                        "passed": bool(r["passed"]), "minutes_to_pass": mins})
        return out

    @app.post("/api/attempts/resume")
    def resume_attempt(req: AttemptRequest):
        """Reuse the open attempt (same mode, <6h old, not passed, solution not opened) so the clock keeps running."""
        if req.problem_id not in problems:
            raise HTTPException(404, "unknown problem")
        cutoff = (datetime.now(UTC) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        row = conn.execute(
            """SELECT a.id, a.started_at FROM attempts a
               WHERE a.problem_id = ? AND a.mode = ? AND a.finished_at IS NULL AND a.started_at > ?
                 AND NOT EXISTS (SELECT 1 FROM revisions r WHERE r.attempt_id = a.id AND r.passed = 1)
                 AND NOT EXISTS (SELECT 1 FROM solution_views v WHERE v.attempt_id = a.id AND v.reason = 'stuck')
               ORDER BY a.id DESC LIMIT 1""", (req.problem_id, req.mode, cutoff)).fetchone()
        if row:
            clk = conn.execute("SELECT active_ms FROM attempt_clock WHERE attempt_id = ?", (row["id"],)).fetchone()
            return {"attempt_id": row["id"], "started_at": row["started_at"], "resumed": True,
                    "active_ms": clk["active_ms"] if clk else 0}
        aid = db.start_attempt(conn, req.problem_id, req.mode)
        started = conn.execute("SELECT started_at FROM attempts WHERE id = ?", (aid,)).fetchone()["started_at"]
        return {"attempt_id": aid, "started_at": started, "resumed": False, "active_ms": 0}

    @app.get("/api/problems/{pid}/draft")
    def get_draft(pid: str):
        row = conn.execute("SELECT code, attempt_id, updated_at FROM drafts WHERE problem_id = ?", (pid,)).fetchone()
        if not row:
            return {"exists": False}
        return {"exists": True, "code": row["code"], "attempt_id": row["attempt_id"], "updated_at": row["updated_at"]}

    @app.put("/api/problems/{pid}/draft")
    @app.post("/api/problems/{pid}/draft")  # POST so navigator.sendBeacon can flush on page leave
    def put_draft(pid: str, req: DraftRequest):
        if pid not in problems:
            raise HTTPException(404, "unknown problem")
        conn.execute(
            "INSERT INTO drafts(problem_id, code, attempt_id) VALUES (?,?,?) ON CONFLICT(problem_id) DO UPDATE SET "
            "code = excluded.code, attempt_id = excluded.attempt_id, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')",
            (pid, req.code, req.attempt_id))
        conn.commit()
        if req.attempt_id is not None:
            _save_clock(conn, req.attempt_id, _clamp_active(conn, req.attempt_id, req.active_ms))
        return {"saved": True}

    @app.delete("/api/problems/{pid}/draft")
    def delete_draft(pid: str):
        conn.execute("DELETE FROM drafts WHERE problem_id = ?", (pid,))
        conn.commit()
        return {"deleted": True}

    @app.post("/api/attempts")
    def new_attempt(req: AttemptRequest):
        if req.problem_id not in problems:
            raise HTTPException(404, "unknown problem")
        return {"attempt_id": db.start_attempt(conn, req.problem_id, req.mode)}

    @app.post("/api/attempts/{aid}/run")
    def run_code(aid: int, req: RunRequest):
        row = conn.execute("SELECT problem_id FROM attempts WHERE id = ?", (aid,)).fetchone()
        if not row:
            raise HTTPException(404, "unknown attempt")
        result = registry.run_problem(req.code, problems[row["problem_id"]])
        payload = [dataclasses.asdict(r) for r in result.results]
        active = _clamp_active(conn, aid, req.active_ms)
        seq = db.add_revision(conn, aid, req.code, result.passed, json.dumps(payload), result.elapsed_ms, active)
        _save_clock(conn, aid, active)
        if result.passed:  # first pass of an attempt = one spaced-repetition review
            started = conn.execute("SELECT started_at FROM attempts WHERE id = ?", (aid,)).fetchone()["started_at"]
            minutes = (active / 60000) if active is not None else (datetime.now(UTC) - _ts(started)).total_seconds() / 60
            p = problems[row["problem_id"]]
            srs.review(conn, p.id, aid, ease_for(True, 0, minutes, p.target_minutes), "pass")
        # Hidden test names/messages are masked in the response; stored in full.
        shown = [r if not r["hidden"] else {**r, "name": "hidden test", "message": ""} for r in payload]
        return {"seq": seq, "passed": result.passed, "timed_out": result.timed_out,
                "elapsed_ms": result.elapsed_ms, "results": shown,
                "stdout": result.stdout, "stderr": result.stderr}

    @app.post("/api/scratch")
    def scratch(req: ScratchRequest):
        return registry.run_scratch(req.code, req.stdin, problems.get(req.problem_id))

    @app.get("/api/attempts/{aid}/revisions")
    def list_revisions(aid: int):
        return [
            {"seq": r["seq"], "code": r["code"], "passed": bool(r["passed"]),
             "elapsed_ms": r["elapsed_ms"], "created_at": r["created_at"]}
            for r in db.revisions(conn, aid)
        ]

    app.include_router(make_router(problems, conn))  # interview mode
    app.include_router(make_eval_router(problems, conn))  # evaluation + progress
    app.include_router(make_plan_router(problems, conn))  # study planner
    app.include_router(make_questions_router(problems, conn))  # question catalog
    app.include_router(make_modules_router(problems, conn))  # learning modules
    app.include_router(make_whiteboard_router(problems, conn))  # whiteboard practice log + schedule

    @app.get("/api/guides/{guide_name}")
    def get_guide(guide_name: str):
        guide_map = {
            "curriculum": DRILLPAD_DIR / "CURRICULUM_GUIDE.md",
            "tracks": DRILLPAD_DIR / "TRACKS.md",
            "roles": DRILLPAD_DIR / "ROLES.md",
            "interview-success": DRILLPAD_DIR / "INTERVIEW_SUCCESS_CRITERIA.md",
            "behavioral": DRILLPAD_DIR / "BEHAVIORAL_AND_STORYTELLING.md",
            "technical": DRILLPAD_DIR / "TECHNICAL_INTERVIEW_TACTICS.md",
            "master-plan": ROOT_DIR / "INTERVIEW_PREP_MASTER_PLAN.md",
            "role-customization": DRILLPAD_DIR / "ROLE_CUSTOMIZATION_GUIDE.md",
            "positioning": DRILLPAD_DIR / "CANDIDATE_POSITIONING_STRATEGY.md",
            "wealth": DRILLPAD_DIR / "WEALTH_CREATION_PATHS.md",
            "pmf-shapes": DRILLPAD_DIR / "SIDE_PROJECT_PMF_SHAPES.md",
            "durable-skills": DRILLPAD_DIR / "DURABLE_SKILLS_NEXT_5_YEARS.md",
            "resume-claims": DRILLPAD_DIR / "RESUME_CLAIM_WALKTHROUGHS.md",
            "firm-rubrics": DRILLPAD_DIR / "FIRM_SPECIFIC_INTERVIEW_RUBRICS.md",
        }
        if guide_name not in guide_map:
            raise HTTPException(status_code=404, detail="Guide not found")
        path = guide_map[guide_name]
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Guide file not found: {path}")
        with open(path, 'r') as f:
            content = f.read()
        return {"markdown": content}

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/home")
    def home_page():
        return FileResponse(STATIC / "home.html")

    @app.get("/guides")
    def guides_page():
        return FileResponse(STATIC / "guides.html")

    @app.get("/guide")
    def guide_page():
        return FileResponse(STATIC / "guide.html")

    @app.get("/learn")
    def learn_page():
        return FileResponse(STATIC / "learn.html")

    @app.get("/practice")
    def practice_page():
        return FileResponse(STATIC / "index.html")

    @app.get("/questions")
    def questions_page():
        return FileResponse(STATIC / "questions.html")

    @app.get("/plan")
    def plan_page():
        return FileResponse(STATIC / "plan.html")

    @app.get("/progress")
    def progress_page():
        return FileResponse(STATIC / "progress.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
