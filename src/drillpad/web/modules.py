"""Learning modules (lessons as markdown) with progress and links into practice problems."""

import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from drillpad.core import paths
from drillpad.evaluation.engine import apply_profile
from drillpad.evaluation.firms import GENERIC
from drillpad.evaluation.progress import _rows
from drillpad.planner.engine import BAR

MODULES_DIR = Path(__file__).resolve().parent.parent / "content" / "modules"
PATHS_FILE = Path(__file__).resolve().parent.parent / "content" / "paths.yaml"
PRIVATE_STAGE = {"stage_id": "99-private", "stage_title": "Private (local only)"}
log = logging.getLogger(__name__)


def _load_paths() -> dict:
    """Load learning paths configuration; fall back to alphabetical order if it is missing or malformed."""
    try:
        if PATHS_FILE.exists():
            return yaml.safe_load(PATHS_FILE.read_text()) or {}
    except (OSError, yaml.YAMLError) as e:
        log.warning("ignoring unreadable %s: %s", PATHS_FILE, e)
    return {}


def _read_module(f: Path, private: bool) -> dict:
    d = yaml.safe_load(f.read_text())
    d["_dir"], d["_private"] = f.parent, private
    return d


def _load() -> dict[str, dict]:
    """Bundled modules, plus any in the private overlay (<data dir>/private/modules). Bundled ids win on a clash."""
    out = {}
    for f in sorted(MODULES_DIR.glob("*/module.yaml")):
        d = _read_module(f, False)
        out[d["id"]] = d
    for f in sorted((paths.private_dir() / "modules").glob("*/module.yaml")):
        try:
            d = _read_module(f, True)
        except (OSError, yaml.YAMLError) as e:
            log.warning("skipping private module %s: %s", f, e)
            continue
        if d.get("id") in out:
            log.warning("private module %s shadows a bundled module id; ignored", d.get("id"))
            continue
        out[d["id"]] = d
    return out


def make_router(problems: dict, conn) -> APIRouter:
    router = APIRouter(prefix="/api")

    def done_set() -> set[tuple[str, str]]:
        return {(r["module_id"], r["lesson_id"]) for r in conn.execute("SELECT module_id, lesson_id FROM lesson_progress")}

    def practice_status() -> dict[str, dict]:
        latest = {e["problem_id"]: e for e in _rows(conn)}
        attempted = {r["problem_id"] for r in conn.execute("SELECT DISTINCT problem_id FROM attempts")}
        out = {}
        for pid, p in problems.items():
            ev = latest.get(pid)
            score = apply_profile(ev["fr"], GENERIC).total if ev else None
            status = "passing" if score is not None and score >= BAR else "attempted" if (ev or pid in attempted) else "todo"
            out[pid] = {"id": pid, "title": p.title, "language": p.language, "level": p.bar_level, "status": status}
        return out

    @router.get("/modules")
    def modules():
        done, mods = done_set(), _load()
        ps = practice_status()
        paths = _load_paths()

        # Build stage lookup: module_id -> (stage_id, stage_title, position_in_stage)
        stage_lookup = {}
        if paths and "stages" in paths:
            for stage in paths["stages"]:
                for idx, module_id in enumerate(stage.get("modules", [])):
                    stage_lookup[module_id] = {
                        "stage_id": stage["id"],
                        "stage_title": stage["title"],
                        "stage_position": idx + 1,
                        "stage_size": len(stage.get("modules", []))
                    }

        res = []
        for m in mods.values():
            lessons = []
            for ls in m["lessons"]:
                practice = [ps.get(i, {"id": i, "title": i, "language": "?", "level": 0, "status": "missing"})
                            for i in ls.get("practice", [])]
                lessons.append({"id": ls["id"], "title": ls["title"], "written": (m["_dir"] / "lessons" / f"{ls['id']}.md").exists(),
                                "done": (m["id"], ls["id"]) in done, "practice": practice})

            module_entry = {"id": m["id"], "title": m["title"], "language": m["language"], "description": m["description"],
                        "lessons": lessons, "done": sum(1 for x in lessons if x["done"]),
                        "practice_passing": sum(1 for x in lessons for p in x["practice"] if p["status"] == "passing")}

            # Add stage info if available
            if m.get("_private"):
                module_entry.update(PRIVATE_STAGE, stage_position=len(res) + 1, private=True)
            elif m["id"] in stage_lookup:
                stage_info = stage_lookup[m["id"]]
                module_entry["stage_id"] = stage_info["stage_id"]
                module_entry["stage_title"] = stage_info["stage_title"]
                module_entry["stage_position"] = stage_info["stage_position"]

            res.append(module_entry)

        # Sort by stage order, then by position within stage
        def sort_key(m):
            if "stage_id" in m:
                stage_id = m["stage_id"]
                # Extract numeric prefix for sorting (e.g., "0-thinking-tools" -> 0)
                stage_num = int(stage_id.split("-")[0]) if stage_id[0].isdigit() else 999
                return (stage_num, m.get("stage_position", 0), m["id"])
            else:
                return (999, 0, m["id"])  # Unsorted modules at end

        res.sort(key=sort_key)
        return res

    @router.get("/modules/{mid}/{lid}")
    def lesson(mid: str, lid: str):
        mods = _load()
        if mid not in mods or lid not in {x["id"] for x in mods[mid]["lessons"]}:
            raise HTTPException(404, "unknown lesson")
        f = mods[mid]["_dir"] / "lessons" / f"{lid}.md"
        text = f.read_text() if f.exists() else "_This lesson has not been written yet._"
        return {"module": mid, "lesson": lid, "markdown": text, "written": f.exists()}

    @router.post("/modules/{mid}/{lid}/done")
    def mark(mid: str, lid: str, done: bool = True):
        mods = _load()
        if mid not in mods or lid not in {x["id"] for x in mods[mid]["lessons"]}:
            raise HTTPException(404, "unknown lesson")
        if done:
            conn.execute("INSERT OR IGNORE INTO lesson_progress(module_id, lesson_id) VALUES (?, ?)", (mid, lid))
        else:
            conn.execute("DELETE FROM lesson_progress WHERE module_id = ? AND lesson_id = ?", (mid, lid))
        conn.commit()
        return {"done": done}

    return router
