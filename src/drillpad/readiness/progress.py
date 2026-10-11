"""Per-level progress from stored attempts, scored per problem (bar_level) with the readiness model.

A solve = an attempt with a passing revision. elapsed = first passing revision time - attempt start.
Hints are 0 for practice attempts (interview hints are not joined in yet).
Thresholds come from levels.yaml (initial heuristics, not calibrated).
"""

from datetime import UTC, datetime

from drillpad.core.models import Problem
from drillpad.readiness.model import (
    Config,
    Level,
    LevelReadiness,
    Solve,
    level_readiness,
)

_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _ts(s: str) -> datetime:
    return datetime.strptime(s, _FMT).replace(tzinfo=UTC)


def solves_by_problem(conn, problems: dict[str, Problem]) -> dict[str, list[Solve]]:
    rows = conn.execute(
        """SELECT a.id, a.problem_id, a.started_at, r.created_at AS solved_at, r.active_ms
           FROM attempts a JOIN revisions r
             ON r.id = (SELECT MIN(id) FROM revisions WHERE attempt_id = a.id AND passed = 1)"""
    ).fetchall()
    out: dict[str, list[Solve]] = {}
    for r in rows:
        p = problems.get(r["problem_id"])
        if not p:
            continue
        solved_at = _ts(r["solved_at"])
        minutes = (max(0.0, r["active_ms"] / 60000) if r["active_ms"] is not None
                   else max(0.0, (solved_at - _ts(r["started_at"])).total_seconds() / 60))
        out.setdefault(p.id, []).append(
            Solve(passed=True, hints_used=0, elapsed_min=minutes, target_min=p.target_minutes, at=solved_at)
        )
    return out


def level_progress(cfg: Config, problems: dict[str, Problem], solves: dict[str, list[Solve]]) -> list[dict]:
    result = []
    for key, lv in cfg.levels.items():
        n = int(key[1:])
        ids = [p.id for p in problems.values() if p.bar_level == n]
        solved = [i for i in ids if solves.get(i)]
        if ids:
            r: LevelReadiness = level_readiness(Level(key, lv.name, {i: 1.0 for i in ids}), solves, cfg.heuristics)
            readiness, ready, mastered = r.readiness, r.ready, r.mastered
        else:
            readiness, ready, mastered = 0.0, False, 0
        result.append({
            "key": key, "name": lv.name, "readiness": round(readiness, 3), "ready": ready,
            "problems": len(ids), "solved": len(solved), "mastered": mastered,
        })
    return result
