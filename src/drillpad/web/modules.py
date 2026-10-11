"""Learning modules (lessons as markdown) with progress and links into practice problems."""

import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from drillpad.core import curricula as cur
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


def _load_all() -> tuple[dict[str, dict], dict[str, cur.Curriculum]]:
    """Every module (bundled, private overlay, and curriculum-owned) and every curriculum, including the built-in `core`
    track from paths.yaml and a `private` track for overlay modules that no curriculum claims. Bundled ids win on a clash."""
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
    plain = dict(out)
    found, problems = cur.load_curricula(set(plain))
    for p in problems:
        log.warning("curricula: %s", p)
    for c in found.values():
        for gid, mdir in cur.owned_modules(c).items():
            if gid in out:
                continue
            try:
                d = yaml.safe_load((mdir / "module.yaml").read_text())
            except (OSError, yaml.YAMLError) as e:
                log.warning("skipping module %s: %s", gid, e)
                continue
            d["id"], d["_dir"], d["_private"], d["_curriculum"] = gid, mdir, c.source == "private", c.id
            out[gid] = d
    all_c = {cur.CORE_ID: cur.core_from_paths(_load_paths(), {m for m, d in plain.items() if not d["_private"]})}
    all_c.update(found)
    lonely = sorted(m for m, d in plain.items() if d["_private"])
    if lonely:
        all_c["private"] = cur.Curriculum(
            id="private", title="Private (local only)", source="private", status="active",
            summary="Modules from your private overlay that no curriculum claims. They never leave this machine.",
            levels=[cur.Level(id="local", title="Local only", units=[
                cur.Unit(key=m, module_id=m, title="", summary="", owned=False, status="ready") for m in lonely])])
    return out, all_c


def _load() -> dict[str, dict]:
    return _load_all()[0]


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
        done = done_set()
        mods, all_c = _load_all()
        ps = practice_status()
        paths = _load_paths()
        in_curricula: dict[str, list[str]] = {}
        for c in all_c.values():
            for u in c.units():
                in_curricula.setdefault(u.module_id, []).append(c.id)

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

            module_entry["curriculum_ids"] = in_curricula.get(m["id"], [])
            if m.get("_private"):
                module_entry["private"] = True
            if m.get("_curriculum"):
                module_entry["curriculum_id"] = m["_curriculum"]
            # Add stage info if available
            if m.get("_private") and not m.get("_curriculum"):
                module_entry.update(PRIVATE_STAGE, stage_position=len(res) + 1, private=True)
            elif m["id"] in stage_lookup:
                stage_info = stage_lookup[m["id"]]
                module_entry["stage_id"] = stage_info["stage_id"]
                module_entry["stage_title"] = stage_info["stage_title"]
                module_entry["stage_position"] = stage_info["stage_position"]

            res.append(module_entry)

        # Sort by stage order, then by position within stage
        def sort_key(m):
            if m.get("curriculum_id"):
                return (500, 0, m["id"])  # curriculum-owned modules after the core stages
            if "stage_id" in m:
                stage_id = m["stage_id"]
                # Extract numeric prefix for sorting (e.g., "0-thinking-tools" -> 0)
                stage_num = int(stage_id.split("-")[0]) if stage_id[0].isdigit() else 999
                return (stage_num, m.get("stage_position", 0), m["id"])
            else:
                return (999, 0, m["id"])  # Unsorted modules at end

        res.sort(key=sort_key)
        return res

    @router.get("/curricula")
    def curricula():
        """Every curriculum with its levels and units (ready or planned), plus progress counted from your lesson checkmarks."""
        done = done_set()
        mods, all_c = _load_all()
        order = {"builtin": 0, "bundled": 1, "external": 2, "private": 3}
        out = []
        for c in sorted(all_c.values(), key=lambda c: (order.get(c.source, 9), c.id == "private", c.id)):
            lessons = finished = ready = planned = 0
            levels = []
            for lv in c.levels:
                units = []
                for u in lv.units:
                    m = mods.get(u.module_id) if u.status == "ready" else None
                    n = len(m["lessons"]) if m else 0
                    d = sum(1 for ls in (m["lessons"] if m else []) if (u.module_id, ls["id"]) in done)
                    first = next((ls["id"] for ls in (m["lessons"] if m else [])
                                  if (m["_dir"] / "lessons" / f"{ls['id']}.md").exists()), None)
                    lessons, finished = lessons + n, finished + d
                    ready, planned = ready + (u.status == "ready"), planned + (u.status == "planned")
                    units.append({"module_id": u.module_id, "key": u.key, "owned": u.owned, "status": u.status,
                                  "title": (m["title"] if m else u.title) or u.key, "summary": u.summary or (m["description"] if m else ""),
                                  "lessons": n, "done": d, "first_lesson": first})
                levels.append({"id": lv.id, "title": lv.title, "units": units})
            out.append({"id": c.id, "title": c.title, "summary": c.summary, "audience": c.audience, "level": c.level,
                        "status": c.status, "version": c.version, "source": c.source,
                        "requires": {"curricula": c.requires_curricula, "modules": c.requires_modules},
                        "capstones": c.capstones, "levels": levels,
                        "progress": {"lessons": lessons, "done": finished, "ready_units": ready, "planned_units": planned}})
        return out

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
