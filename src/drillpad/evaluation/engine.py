"""Rubric scoring. Every dimension is stored as a 0..1 fraction (None = not assessed) so the same
attempt can be re-scored under any firm profile. Unassessed dimensions earn 0 toward the bar (conservative)."""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime

from drillpad.core.models import Problem
from drillpad.core.taxonomy import DIMENSIONS
from drillpad.evaluation import bigo
from drillpad.evaluation.firms import Profile

_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _ts(s: str) -> datetime:
    return datetime.strptime(s, _FMT).replace(tzinfo=UTC)


@dataclass
class Fractions:
    """Raw 0..1 per dimension plus the evidence behind it."""
    dims: dict[str, float | None]
    detail: dict = field(default_factory=dict)


def solve_minutes(rev, started_at: str) -> float:
    """Minutes spent to reach this revision: active (un-paused) time if recorded, else wall-clock."""
    try:
        active = rev["active_ms"]
    except (KeyError, IndexError):
        active = None
    if active is not None:
        return max(0.0, active / 60000)
    return max(0.0, (_ts(rev["created_at"]) - _ts(started_at)).total_seconds() / 60)


def _pass_map(results: list[dict]) -> dict[str, bool]:
    return {r["name"]: bool(r["passed"]) for r in results}


def _gather_cumulative_tests(problem: Problem):
    """Gather all cumulative tests from stages or flat test list."""
    if problem.stages:
        result = []
        for stage in problem.stages:
            result.extend(stage.tests)
        return result
    else:
        return problem.tests


def _highest_passed_stage(results: list[dict]) -> int:
    """Return the highest stage where all cumulative tests passed."""
    if not results:
        return -1
    stages = {r.get("stage", 0) for r in results}
    passed_stages = []
    for stage in sorted(stages):
        if all(r["passed"] for r in results if r.get("stage", 0) <= stage):
            passed_stages.append(stage)
    return max(passed_stages) if passed_stages else -1


def raw_fractions(
    problem: Problem, revisions: list[sqlite3.Row], started_at: str, profile: Profile,
    complexity_answers: dict | None = None, extension_answers: list[dict] | None = None,
    communication: dict | None = None, gave_up: bool = False,
) -> Fractions:
    detail: dict = {}
    dims: dict[str, float | None] = dict.fromkeys(DIMENSIONS)
    if not revisions:
        return Fractions(dict.fromkeys(DIMENSIONS, 0.0), {"note": "no runs", "gave_up": gave_up})
    first, last = json.loads(revisions[0]["results_json"]), json.loads(revisions[-1]["results_json"])
    f_map, l_map = _pass_map(first), _pass_map(last)

    # Stage gating: compute highest passed stage
    highest_stage = _highest_passed_stage(last)
    if problem.stages:
        num_stages = len(problem.stages)
        detail["stage_progress"] = f"{highest_stage + 1}/{num_stages}" if highest_stage >= 0 else "0/{num_stages}"
        # For gating: only count correctness if all required stages pass
        # Stages 1-3 must pass tests; stage 4+ only needs self-graded design
        required_stages = min(3, num_stages - 1)  # stages 0,1,2 for 3+ stages; else all stages
        all_required_pass = highest_stage >= required_stages
    else:
        all_required_pass = True

    # correctness: share of ALL tests passing, but only if all required stages pass
    all_tests = _gather_cumulative_tests(problem)
    dims["correctness"] = (sum(l_map.values()) / len(all_tests)) if all_tests else 0.0
    if problem.stages and not all_required_pass:
        dims["correctness"] = 0.0
    detail["tests_passed"] = [sum(l_map.values()), len(all_tests)] if all_tests else [0, 0]

    # edge cases: tagged tests, half weight on first run (live you do not get a second look), half on final
    all_tests = _gather_cumulative_tests(problem)
    tagged = [t for t in all_tests if t.tags] or [t for t in all_tests if t.hidden]
    edge: dict[str, list[int]] = {}
    for t in tagged:
        for tag in (t.tags or ["untagged"]):
            e = edge.setdefault(tag, [0, 0, 0])  # first-run pass, final pass, total
            e[0] += int(f_map.get(t.name, False))
            e[1] += int(l_map.get(t.name, False))
            e[2] += 1
    if tagged:
        fr = sum(1 for t in tagged if f_map.get(t.name)) / len(tagged)
        fin = sum(1 for t in tagged if l_map.get(t.name)) / len(tagged)
        dims["edge_cases"] = 0.5 * fr + 0.5 * fin
    else:
        dims["edge_cases"] = dims["correctness"]
    if problem.stages and not all_required_pass:
        dims["edge_cases"] = 0.0
    detail["edge_by_tag"] = edge

    # complexity: per listed op, time and space each graded against canonical (60/40)
    if problem.complexity:
        ans = complexity_answers or {}
        per_op, total = {}, 0.0
        for c in problem.complexity:
            a = ans.get(c.op, {})
            ts_ = bigo.score(a.get("time", ""), c.time, c.accepted_time)
            ss_ = bigo.score(a.get("space", ""), c.space, c.accepted_space)
            per_op[c.op] = {"time": ts_, "space": ss_, "expected": [c.time, c.space]}
            total += 0.6 * ts_ + 0.4 * ss_
        dims["complexity"] = total / len(problem.complexity)
        detail["complexity"] = per_op

    # pace: minutes from attempt start to first fully passing revision, vs target
    # Only count if all required stages pass
    solved_idx = next((i for i, r in enumerate(revisions) if r["passed"]), None)
    target = profile.pace_by_level.get(problem.bar_level) or problem.target_minutes
    if solved_idx is None or (problem.stages and not all_required_pass):
        dims["pace"] = 0.0
        detail["pace"] = {"solved": False, "target_min": target}
    else:
        mins = solve_minutes(revisions[solved_idx], started_at)
        dims["pace"] = 1.0 if mins <= target else max(0.0, 1 - (mins - target) / (0.5 * target))
        detail["pace"] = {"solved": True, "minutes": round(mins, 1), "target_min": target}

    # quality: debugging efficiency = runs needed to first pass, minus hint cost
    # Only count if all required stages pass
    if solved_idx is None or (problem.stages and not all_required_pass):
        dims["quality"] = 0.0
    else:
        runs = solved_idx + 1
        base = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.25, 5: 0.25}.get(runs, 0.1)
        hints = (communication or {}).get("hints_used", 0) or 0
        dims["quality"] = max(0.0, base - 0.15 * hints)
        detail["runs_to_pass"] = runs

    # communication: only assessed when interview data is supplied
    if communication and communication.get("assessed"):
        am, fc = communication.get("approach_min"), communication.get("first_code_min")
        stated_first = am is not None and (fc is None or am <= fc)
        in_time = am is not None and am <= profile.approach_by_minute
        no_hints = (communication.get("hints_used") or 0) == 0
        dims["communication"] = 0.4 * stated_first + 0.3 * in_time + 0.3 * no_hints
        detail["communication"] = {"approach_min": am, "first_code_min": fc, "stated_first": stated_first}

    # extensions: key points credited across ALL extensions; unanswered counts as zero
    # If problem has stages, blend stage completion (test-enforced) with self-graded key points
    if problem.extensions or problem.stages:
        stage_fraction = 0.0
        if problem.stages:
            stage_fraction = (highest_stage + 1) / len(problem.stages) if highest_stage >= 0 else 0.0
            detail["stages"] = {"passed": highest_stage + 1, "total": len(problem.stages), "fraction": round(stage_fraction, 2)}

        if problem.extensions:
            pts = sum(len(e.key_points) for e in problem.extensions)
            got = 0
            for a in extension_answers or []:
                i = a.get("idx")
                if isinstance(i, int) and 0 <= i < len(problem.extensions):
                    n = len(problem.extensions[i].key_points)
                    got += min(n, sum(1 for c in (a.get("covered") or [])[:n] if c))
            key_points_fraction = got / pts if pts else 0.0
            detail["extensions"] = [got, pts]
        else:
            key_points_fraction = 0.0

        # Blend stage and key points: 50/50
        if problem.stages and problem.extensions:
            dims["extensions"] = 0.5 * stage_fraction + 0.5 * key_points_fraction
        elif problem.stages:
            dims["extensions"] = stage_fraction
        else:
            dims["extensions"] = key_points_fraction
    if gave_up:
        # Opened the north star while stuck: only pre-peek correctness/edge credit survives; answers given
        # after seeing the solution are untrustworthy, so they earn nothing. Retry closed-book to earn credit.
        for d in ("pace", "quality", "complexity", "extensions"):
            if dims.get(d) is not None:
                dims[d] = 0.0
        detail["gave_up"] = True
    return Fractions(dims, detail)


@dataclass
class Score:
    firm_id: str
    total: float
    pass_score: int
    verdict: str  # PASS | NO-PASS
    per_dim: dict[str, dict]
    unassessed: list[str]
    failed_floors: list[str]
    fixes: list[dict]


def apply_profile(fr: Fractions, profile: Profile) -> Score:
    per_dim, total, unassessed = {}, 0.0, []
    for d in DIMENSIONS:
        w = profile.weights.get(d, 0)
        frac = fr.dims.get(d)
        if frac is None:
            unassessed.append(d)
        earned = (frac or 0.0) * w
        total += earned
        per_dim[d] = {"weight": w, "fraction": frac, "earned": round(earned, 1), "left": round(w - earned, 1)}
    failed = [f"{d} {round((fr.dims.get(d) or 0) * 100)}% < floor {round(m * 100)}%"
              for d, m in profile.floors.items() if (fr.dims.get(d) or 0) < m]
    verdict = "PASS" if total >= profile.pass_score and not failed else "NO-PASS"
    fixes = _fixes(fr, per_dim, profile)
    return Score(profile.id, round(total, 1), profile.pass_score, verdict, per_dim, unassessed, failed, fixes)


def _fixes(fr: Fractions, per_dim: dict, profile: Profile) -> list[dict]:
    """Highest points-recoverable first, with the concrete cause."""
    out = []
    if fr.detail.get("gave_up"):
        out.append({"dimension": "all", "points_left": 0, "why": "You opened the solution while stuck: retry closed-book (Recall) to earn this credit."})
    for d, v in sorted(per_dim.items(), key=lambda kv: -kv[1]["left"]):
        if v["left"] <= 0.5:
            continue
        why = {
            "correctness": "Failing tests in the final revision." if fr.dims.get("correctness") else "No passing tests.",
            "edge_cases": "Weak tags: " + (", ".join(t for t, e in fr.detail.get("edge_by_tag", {}).items() if e[0] < e[2]) or "—"),
            "complexity": "Wrong/missing big-O for: " + (", ".join(
                op for op, x in fr.detail.get("complexity", {}).items() if x["time"] < 1 or x["space"] < 1) or "—"),
            "pace": f"Target {fr.detail.get('pace', {}).get('target_min')} min; took {fr.detail.get('pace', {}).get('minutes', 'never solved')}.",
            "communication": "Not assessed: run an Interview-mode session." if fr.dims.get("communication") is None else "State approach before coding, within the approach deadline, without hints.",
            "extensions": "Answer the follow-ups; credit is per key point covered.",
            "quality": "Pass on the first run: think and trace before pressing Run.",
        }[d]
        out.append({"dimension": d, "points_left": v["left"], "why": why})
    return out[:4]


def store_evaluation(conn: sqlite3.Connection, attempt_id: int, problem_id: str, fr: Fractions, submissions: dict) -> int:
    cur = conn.execute(
        "INSERT INTO evaluations(attempt_id, problem_id, dims_json, detail_json, submissions_json) VALUES (?,?,?,?,?)",
        (attempt_id, problem_id, json.dumps(fr.dims), json.dumps(fr.detail), json.dumps(submissions)),
    )
    conn.commit()
    return cur.lastrowid
