"""Central progress aggregation. 'Progress' here means, concretely:
  1. Bar score per firm profile  (latest evaluation per problem, re-scored under that firm's weights)
  2. Coverage                    (how many of the firm's problems you have evaluated at all)
  3. Skill profile               (average 0..1 per rubric dimension)
  4. Edge-case map               (miss rate per edge category, first run vs final)
  5. Trend and activity          (are scores rising? are you doing reps?)
"""

import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from drillpad.core.models import Problem
from drillpad.core.taxonomy import DIMENSIONS
from drillpad.evaluation.engine import Fractions, apply_profile
from drillpad.evaluation.firms import Profile

READY_COVERAGE = 0.8  # share of a firm's problems that must have an evaluation before READY is possible


def _rows(conn):
    return [
        {"id": r["id"], "problem_id": r["problem_id"], "created_at": r["created_at"],
         "fr": Fractions(json.loads(r["dims_json"]), json.loads(r["detail_json"]))}
        for r in conn.execute("SELECT * FROM evaluations ORDER BY id").fetchall()
    ]


def build(conn, problems: dict[str, Problem], profiles: dict[str, Profile], firm_id: str) -> dict:
    evals = _rows(conn)
    latest: dict[str, dict] = {}
    for e in evals:
        latest[e["problem_id"]] = e
    profile = profiles.get(firm_id) or profiles["generic"]

    def firm_view(p: Profile) -> dict:
        pids = [i for i in (p.problem_ids or list(problems)) if i in problems]
        scored = {i: apply_profile(latest[i]["fr"], p) for i in pids if i in latest}
        n, k = len(pids), len(scored)
        mean_attempted = sum(s.total for s in scored.values()) / k if k else 0.0
        mean_all = sum(s.total for s in scored.values()) / n if n else 0.0
        passing = sum(1 for s in scored.values() if s.verdict == "PASS")
        coverage = k / n if n else 0.0
        reasons = []
        if coverage < READY_COVERAGE:
            reasons.append(f"coverage {k}/{n} problems evaluated (need {int(READY_COVERAGE * 100)}%)")
        if k and mean_attempted < p.pass_score:
            reasons.append(f"average {mean_attempted:.0f} < pass score {p.pass_score}")
        if k and passing < k:
            reasons.append(f"{k - passing} evaluated problem(s) below the bar")
        return {"id": p.id, "name": p.name, "pass_score": p.pass_score, "problems": n, "evaluated": k,
                "passing": passing, "coverage": round(coverage, 2), "mean_attempted": round(mean_attempted, 1),
                "bar_score": round(mean_all, 1), "ready": not reasons, "reasons": reasons, "weights": p.weights}

    firms = [firm_view(p) for p in profiles.values()]
    firms.sort(key=lambda f: (-f["bar_score"], f["id"]))

    # skill profile + trend
    dim_vals: dict[str, list[float]] = defaultdict(list)
    for e in latest.values():
        for d in DIMENSIONS:
            v = e["fr"].dims.get(d)
            if v is not None:
                dim_vals[d].append(v)
    skill = {d: round(sum(v) / len(v), 3) if v else None for d, v in ((d, dim_vals[d]) for d in DIMENSIONS)}
    timeline = [{"at": e["created_at"], "problem_id": e["problem_id"], "total": apply_profile(e["fr"], profile).total}
                for e in evals]
    last10, prev10 = [t["total"] for t in timeline[-10:]], [t["total"] for t in timeline[-20:-10]]
    delta = round(sum(last10) / len(last10) - sum(prev10) / len(prev10), 1) if last10 and prev10 else None

    # edge-case map across all evaluations
    edge: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for e in evals:
        for tag, (first, final, total) in e["fr"].detail.get("edge_by_tag", {}).items():
            edge[tag][0] += first
            edge[tag][1] += final
            edge[tag][2] += total
    edge_map = sorted(
        ({"tag": t, "first_run_miss": round(1 - a / n, 2), "final_miss": round(1 - b / n, 2), "samples": n}
         for t, (a, b, n) in edge.items() if n), key=lambda x: -x["first_run_miss"])

    # complexity accuracy (latest per problem)
    cx = []
    for pid, e in latest.items():
        for op, x in e["fr"].detail.get("complexity", {}).items():
            if x["time"] < 1 or x["space"] < 1:
                cx.append({"problem_id": pid, "op": op, "time_ok": x["time"] >= 1, "space_ok": x["space"] >= 1,
                           "expected": x["expected"]})

    # activity: attempts per day, last 14 days
    since = (datetime.now(UTC) - timedelta(days=13)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT substr(started_at,1,10) d, COUNT(*) n FROM attempts WHERE substr(started_at,1,10) >= ? GROUP BY d", (since,)
    ).fetchall()
    activity = {r["d"]: r["n"] for r in rows}

    # next actions for the selected firm: biggest gaps first, unattempted problems included
    pv = firm_view(profile)
    actions = []
    for pid in [i for i in (profile.problem_ids or list(problems)) if i in problems]:
        if pid in latest:
            s = apply_profile(latest[pid]["fr"], profile)
            if s.verdict == "PASS":
                continue
            actions.append({"problem_id": pid, "title": problems[pid].title, "score": s.total,
                            "gap": round(profile.pass_score - s.total, 1), "fix": s.fixes[0] if s.fixes else None})
        else:
            actions.append({"problem_id": pid, "title": problems[pid].title, "score": None,
                            "gap": profile.pass_score, "fix": {"dimension": "all", "why": "Not attempted yet."}})
    actions.sort(key=lambda a: (-a["gap"], problems[a["problem_id"]].bar_level))

    return {
        "selected": firm_id if firm_id in profiles else "generic", "firm": pv, "firms": firms,
        "skill": skill, "trend": {"timeline": timeline[-40:], "delta_last10_vs_prev10": delta},
        "edge_map": edge_map, "complexity_misses": cx[:20], "activity": activity, "next": actions[:6],
        "evaluations": len(evals),
        "definition": ("Progress = (1) bar score per firm profile, (2) coverage of that firm's problems, "
                       "(3) per-dimension skill, (4) edge-case miss map, (5) trend + reps. "
                       "A firm is READY only with >=80% coverage and every evaluated problem at or above its pass score."),
    }
