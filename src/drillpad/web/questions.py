"""Full question catalog: canonical coverage per lever joined with the user's attempt/score status."""

from pathlib import Path

import yaml
from fastapi import APIRouter

from drillpad.evaluation.engine import apply_profile
from drillpad.evaluation.firms import GENERIC
from drillpad.evaluation.progress import _rows
from drillpad.planner.engine import BAR, derive_categories
from drillpad.srs import engine as srs

CANON = Path(__file__).resolve().parent.parent / "content" / "canon.yaml"


def make_router(problems: dict, conn) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/questions")
    def questions():
        canon = yaml.safe_load(CANON.read_text())
        latest = {e["problem_id"]: e for e in _rows(conn)}
        attempts = {r["problem_id"]: r["n"] for r in conn.execute(
            "SELECT problem_id, COUNT(*) n FROM attempts GROUP BY problem_id")}

        snap = srs.snapshot(conn)

        def state(pid: str) -> dict:
            if pid not in problems:
                return {"status": "missing"}
            ev = latest.get(pid)
            score = apply_profile(ev["fr"], GENERIC).total if ev else None
            status = "passing" if score is not None and score >= BAR else "attempted" if (ev or attempts.get(pid)) else "todo"
            sc = snap.get(pid)
            return {"status": status, "score": score, "attempts": attempts.get(pid, 0),
                    "recall": sc["retrievability"] if sc else None, "due": bool(sc and sc["due_now"])}

        levers, seen = [], set()
        for lv, d in canon["levers"].items():
            groups: dict[str, list] = {}
            for it in d["items"]:
                seen.add(it["id"])
                p = problems.get(it["id"])
                groups.setdefault(it["group"], []).append({
                    "id": it["id"], "title": p.title if p else it["title"], "level": p.bar_level if p else it["level"],
                    "minutes": p.target_minutes if p else None, "language": p.language if p else None, **state(it["id"])})
            items = [i for g in groups.values() for i in g]
            levers.append({
                "id": lv, "label": d["label"], "basis": d["basis"], "total": len(items),
                "authored": sum(1 for i in items if i["status"] != "missing"),
                "attempted": sum(1 for i in items if i["status"] in ("attempted", "passing")),
                "passing": sum(1 for i in items if i["status"] == "passing"),
                "groups": [{"id": g, "items": v} for g, v in groups.items()]})
        extras = [{"id": p.id, "title": p.title, "level": p.bar_level, "minutes": p.target_minutes, "language": p.language,
                   "categories": derive_categories(p), **state(p.id)} for p in problems.values() if p.id not in seen]
        return {"note": canon.get("note", ""), "levers": levers, "extras": extras, "total_problems": len(problems)}

    return router
