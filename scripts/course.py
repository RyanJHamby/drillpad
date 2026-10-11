#!/usr/bin/env python3
"""Course maintenance: keep counts honest, check integrity, report content health, scaffold additions.

  python scripts/course.py docs                 regenerate the generated parts of TRACKS.md and START_HERE.md
  python scripts/course.py check                integrity + freshness check (exit 1 on problems; run in CI/tests)
  python scripts/course.py report [--stale-days N]   thin lessons, [VERIFY] tags, stale or missing "Last verified"
  python scripts/course.py new-lesson MODULE SLUG "Title"       append a lesson skeleton to an existing module
  python scripts/course.py new-module ID STAGE "Title" [--language systems]   create a module and place it in a stage
  python scripts/course.py new-module ID --private "Title"                    create a LOCAL-ONLY module in the private overlay (never exported)
  python scripts/course.py new-curriculum ID "Title" [--private | --dest DIR]  create a curriculum (bundled, private, or a standalone pack in DIR)
  python scripts/course.py new-module KEY --curriculum CID [--level LID] "Title"   write a module a curriculum owns (or has planned)

Everything here is additive: scaffolds refuse to overwrite, and docs only rewrite marked generated regions.
"""

import argparse
import json
import math
import re
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "src" / "drillpad"
MODULES = PKG / "content" / "modules"
PATHS = PKG / "content" / "paths.yaml"
TRACKS = PKG / "TRACKS.md"
START = ROOT / "START_HERE.md"
THIN_BYTES = 4000
WORDS_PER_MIN = 200  # rough reading speed; hours below are reading-time estimates, not benchmarks
BEGIN, END = "<!-- BEGIN GENERATED (scripts/course.py docs) -->", "<!-- END GENERATED -->"
VERIFIED = re.compile(r"Last verified:\s*(\d{4}-\d{2}-\d{2})")

LESSON_TEMPLATE = """# {title}

Drafted: {today} (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The problem and why it matters
<!-- Why this appears in interviews and in production. -->

## First principles
<!-- Why, not just what. -->

## How it works
<!-- At least 2 ASCII diagrams of the real mechanism. -->

## Worked failure scenario
<!-- What breaks, how you detect it, how you fix it. -->

## Tradeoffs
| Use when | Avoid when |
|---|---|
|  |  |

## Interview questions
<!-- 5+ recall questions with probing follow-ups and model answer outlines, plus one worked exercise. -->

## Checklist
1.
2.
3.
4.
5.

## Common wrong answers

## Related lessons
"""


def load_paths() -> dict:
    return yaml.safe_load(PATHS.read_text()) or {}


def curricula_api():
    sys.path.insert(0, str(ROOT / "src"))
    from drillpad.core import curricula as cur

    return cur


def module_entry(d: Path, y: dict) -> dict:
    lessons = []
    for ls in y.get("lessons", []):
        path = d / "lessons" / f"{ls['id']}.md"
        text = path.read_text() if path.exists() else ""
        lessons.append({"id": ls["id"], "title": ls["title"], "path": path, "exists": path.exists(),
                        "bytes": len(text.encode()), "words": len(text.split()), "text": text})
    return {"dir": d, "yaml": y, "lessons": lessons}


def load_modules() -> dict[str, dict]:
    """Core modules plus modules owned by the repo's bundled curricula (global id `<curriculum>.<key>`)."""
    out = {}
    for f in sorted(MODULES.glob("*/module.yaml")):
        d = yaml.safe_load(f.read_text())
        out[d["id"]] = module_entry(f.parent, d)
    cur = curricula_api()
    found, _ = cur.load_curricula(set(out), sources={"bundled"})
    for cc in found.values():
        for gid, mdir in cur.owned_modules(cc).items():
            y = yaml.safe_load((mdir / "module.yaml").read_text()) or {}
            y["id"] = gid
            out[gid] = {**module_entry(mdir, y), "curriculum": cc.id}
    return out


def bundled_curricula():
    """(curricula, problems) for the repo's own curricula, with reused modules resolved against what is on disk."""
    cur = curricula_api()
    core = {m for m in (p.parent.name for p in MODULES.glob("*/module.yaml"))}
    return cur.load_curricula(core, sources={"bundled"})


def minutes(mod: dict) -> int:
    return sum(math.ceil(ls["words"] / WORDS_PER_MIN) for ls in mod["lessons"])


def hours(mins: int) -> str:
    return f"{mins / 60:.0f}"


def stage_modules(paths: dict, stage_ids: list[str]) -> list[str]:
    by_id = {s["id"]: s for s in paths["stages"]}
    return [m for sid in stage_ids for m in by_id[sid]["modules"]]


def path_module_ids(paths: dict, spec: dict) -> list[str]:
    seen, out = set(), []
    for m in stage_modules(paths, spec["stages"]) + list(spec.get("extra_modules") or []) + list(paths.get("always") or []):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def totals(mods: dict) -> dict:
    return {"n_modules": len(mods), "n_lessons": sum(len(m["lessons"]) for m in mods.values()),
            "n_written": sum(1 for m in mods.values() for ls in m["lessons"] if ls["exists"]),
            "minutes": sum(minutes(m) for m in mods.values())}


def generated_block(mods: dict, paths: dict) -> str:
    t, known = totals(mods), set(mods)
    L = [BEGIN, "",
         (f"_Generated from `content/paths.yaml` and each `module.yaml`. Do not edit by hand; run `python scripts/course.py docs`. "
          f"Reading time is words ÷ {WORDS_PER_MIN} per minute, an estimate that excludes exercises and whiteboarding._"), "",
         f"**{t['n_lessons']} lessons across {t['n_modules']} modules in {len(paths['stages'])} stages, about {hours(t['minutes'])} hours of reading.**", "",
         "## Stages (learn in this order)", ""]
    for st in paths["stages"]:
        ms = [m for m in st["modules"] if m in known]
        L += [f"### Stage {st['id'].split('-')[0]}: {st['title']}", "", st.get("description", ""), "",
              "| Module | Lessons | ~Reading | Learn page |", "|---|---|---|---|"]
        for m in ms:
            L.append(f"| {mods[m]['yaml']['title']} | {len(mods[m]['lessons'])} | {hours(minutes(mods[m]))}h | `/learn?m={m}` |")
        L.append("")
    L += ["## Role paths", "", "Each path lists stages in order, then extra modules, then the always-on modules.", ""]
    for name, spec in paths["paths"].items():
        ids = [m for m in path_module_ids(paths, spec) if m in known]
        n = sum(len(mods[m]["lessons"]) for m in ids)
        mins = sum(minutes(mods[m]) for m in ids)
        L += [f"### {name}", "", f"Stages: {' → '.join(s.split('-')[0] for s in spec['stages'])}"
              + (f" · extra: {', '.join(spec['extra_modules'])}" if spec.get("extra_modules") else ""),
              "", f"{len(ids)} modules, {n} lessons, about {hours(mins)} hours of reading.", ""]
        L += [f"{i}. [{mods[m]['yaml']['title']}](/learn?m={m}) ({len(mods[m]['lessons'])})" for i, m in enumerate(ids, 1)]
        L.append("")
    found, _ = bundled_curricula()
    if found:
        L += ["## Curricula", "", "Focused tracks that reuse core modules and add depth on one subject. Planned units are a roadmap, not yet written.", ""]
        for cc in found.values():
            ready = sum(1 for u in cc.units() if u.status == "ready")
            planned = sum(1 for u in cc.units() if u.status == "planned")
            L += [f"### {cc.title} (`{cc.id}`)", "", cc.summary, "",
                  f"Status: {cc.status} · level: {cc.level or 'n/a'} · {ready} units ready, {planned} planned", ""]
            for lv in cc.levels:
                L.append(f"**{lv.title}**")
                L.append("")
                for u in lv.units:
                    mark = "" if u.status == "ready" else f" _({u.status})_"
                    owned = "" if u.owned else " (core)"
                    label = mods[u.module_id]["yaml"]["title"] if u.module_id in mods else (u.title or u.key)
                    L.append(f"- {label}{owned}{mark}")
                L.append("")
    L += ["## Prerequisites", ""]
    L += [f"- `{m}` needs {', '.join(f'`{r}`' for r in reqs)}" for m, reqs in sorted((paths.get("requires") or {}).items())]
    L += ["", END]
    return "\n".join(L)


def fill_markers(text: str, values: dict) -> str:
    for key, val in values.items():
        text = re.sub(rf"<!--{key}-->.*?<!--/{key}-->", lambda _m, k=key, v=val: f"<!--{k}-->{v}<!--/{k}-->", text)
    return text


def expected_docs(mods: dict, paths: dict) -> dict[Path, str]:
    t = totals(mods)
    out = {}
    if TRACKS.exists():  # a public copy may omit generated docs it does not ship
        tracks = TRACKS.read_text()
        if BEGIN not in tracks or END not in tracks:
            raise SystemExit(f"{TRACKS} is missing the generated-region markers")
        pre, rest = tracks.split(BEGIN, 1)
        out[TRACKS] = pre + generated_block(mods, paths) + rest.split(END, 1)[1]
    if START.exists():
        out[START] = fill_markers(START.read_text(), {"n_lessons": t["n_lessons"], "n_modules": t["n_modules"],
                                                       "n_stages": len(paths["stages"]), "hours": hours(t["minutes"])})
    return out


def cmd_docs(_a) -> int:
    for path, text in expected_docs(load_modules(), load_paths()).items():
        if path.read_text() != text:
            path.write_text(text)
            print(f"updated {path.relative_to(ROOT)}")
    return 0


def problems(mods: dict, paths: dict) -> tuple[list[str], list[str]]:
    errors, warns, placed = [], [], {}
    for st in paths["stages"]:
        for m in st["modules"]:
            if m in placed:
                errors.append(f"module {m} is in stages {placed[m]} and {st['id']}")
            placed[m] = st["id"]
            if m not in mods:
                warns.append(f"paths.yaml lists {m} but it is not on disk yet")
    for m in sorted(m for m in set(mods) - set(placed) if not mods[m].get("curriculum")):
        errors.append(f"module {m} is on disk but not in any stage of paths.yaml (use `new-module` or add it)")
    for m, reqs in (paths.get("requires") or {}).items():
        for r in [m, *reqs]:
            if r not in mods and r not in placed:
                errors.append(f"requires: unknown module {r}")
    for mid, mod in mods.items():
        ids = [ls["id"] for ls in mod["lessons"]]
        errors += [f"{mid}: duplicate lesson id {i}" for i in {i for i in ids if ids.count(i) > 1}]
        warns += [f"{mid}: lesson {ls['id']} is listed in module.yaml but has no file yet (shows as '(coming)' in the app)"
                  for ls in mod["lessons"] if not ls["exists"]]
        files = {p.stem for p in (mod["dir"] / "lessons").glob("*.md")} if (mod["dir"] / "lessons").exists() else set()
        errors += [f"{mid}: lessons/{f}.md exists but is not listed in module.yaml (invisible in the app)" for f in sorted(files - set(ids))]
    errors += [f"curricula: {p}" for p in bundled_curricula()[1]]
    try:
        for path, text in expected_docs(mods, paths).items():
            if path.read_text() != text:
                errors.append(f"{path.relative_to(ROOT)} is stale: run `python scripts/course.py docs`")
    except SystemExit as e:
        errors.append(str(e))
    return errors, warns


def cmd_check(_a) -> int:
    errors, warns = problems(load_modules(), load_paths())
    for w in warns:
        print("warn:", w)
    for e in errors:
        print("error:", e)
    print("ok" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


def cmd_report(a) -> int:
    mods, today = load_modules(), datetime.now().astimezone().date()
    thin, stale, unverified, tags = [], [], 0, []
    for mid, mod in mods.items():
        for ls in mod["lessons"]:
            if not ls["exists"]:
                continue
            ref = f"{mid}/{ls['id']}"
            if ls["bytes"] < THIN_BYTES:
                thin.append((ls["bytes"], ref))
            n = ls["text"].count("[VERIFY")
            if n:
                tags.append((n, ref))
            m = VERIFIED.search(ls["text"])
            if not m:
                unverified += 1
            elif (today - date.fromisoformat(m.group(1))).days > a.stale_days:
                stale.append((m.group(1), ref))
    t = totals(mods)
    print(f"{t['n_lessons']} lessons in {t['n_modules']} modules; {t['n_written']} written")
    print(f"\nThin (< {THIN_BYTES} bytes): {len(thin)}")
    for b, r in sorted(thin):
        print(f"  {b:>6}  {r}")
    print(f"\nOpen [VERIFY] tags: {sum(n for n, _ in tags)} in {len(tags)} lessons")
    for n, r in sorted(tags, reverse=True):
        print(f"  {n:>3}  {r}")
    print(f"\nNo 'Last verified: YYYY-MM-DD' line: {unverified} lessons (add one after you check a lesson against sources)")
    print(f"Verified more than {a.stale_days} days ago: {len(stale)}")
    for d, r in sorted(stale):
        print(f"  {d}  {r}")
    return 0


def append_lesson(mod_dir: Path, lesson_id: str, title: str, order: int, description: str = "TODO") -> None:
    f = mod_dir / "module.yaml"
    text = f.read_text()
    if re.search(r"^lessons:\s*\[\]\s*$", text, re.MULTILINE):
        text = re.sub(r"^lessons:\s*\[\]\s*$", "lessons:", text, flags=re.MULTILINE)
    lines = text.rstrip("\n").split("\n")
    idx = [i for i, ln in enumerate(lines) if re.match(r"^\s*- id:", ln)]
    ind = re.match(r"^(\s*)", lines[idx[-1]]).group(1) if idx else "  "
    tail = lines[idx[-1] + 1:] if idx else lines[next(i for i, ln in enumerate(lines) if ln.startswith("lessons:")) + 1:]
    if any(ln.strip() and not ln.startswith(" ") and not ln.startswith("#") for ln in tail):
        raise SystemExit(f"{f}: `lessons:` is not the last key; add the entry by hand")
    lines += [f"{ind}- id: {lesson_id}", f"{ind}  title: {json.dumps(title)}", f"{ind}  description: {json.dumps(description)}",
              f"{ind}  estimated_duration_minutes: 60", f"{ind}  status: draft", f"{ind}  order: {order}"]
    f.write_text("\n".join(lines) + "\n")


def private_modules_dir() -> Path:
    sys.path.insert(0, str(ROOT / "src"))
    from drillpad.core import paths

    return paths.private_dir() / "modules"


def curriculum_root(cid: str) -> Path | None:
    cur = curricula_api()
    for source, root in cur.roots():
        for d in cur.curriculum_dirs(root):
            cc, _ = cur.read_curriculum(d, source)
            if cc and cc.id == cid:
                return d
    return None


def find_module(module_id: str) -> dict:
    mods = load_modules()
    if module_id in mods:
        return mods[module_id]
    if "." in module_id:  # `<curriculum>.<key>`: a module owned by a bundled, private, or external curriculum
        cid, key = module_id.split(".", 1)
        root = curriculum_root(cid)
        if root and (root / "modules" / key / "module.yaml").exists():
            y = yaml.safe_load((root / "modules" / key / "module.yaml").read_text()) or {}
            return {**module_entry(root / "modules" / key, y), "private": root != ROOT and ROOT not in root.parents}
    d = private_modules_dir() / module_id
    if (d / "module.yaml").exists():
        return {**module_entry(d, yaml.safe_load((d / "module.yaml").read_text())), "private": True}
    raise SystemExit(f"unknown module {module_id}")


def cmd_new_lesson(a) -> int:
    mod = find_module(a.module)
    nums = [int(m.group(1)) for ls in mod["lessons"] if (m := re.match(r"(\d+)-", ls["id"]))]
    nums += [int(m.group(1)) for p in (mod["dir"] / "lessons").glob("*.md") if (m := re.match(r"(\d+)-", p.name))]
    n = max(nums, default=0) + 1
    lid = f"{n:02d}-{a.slug}"
    path = mod["dir"] / "lessons" / f"{lid}.md"
    if path.exists():
        raise SystemExit(f"{path} already exists; nothing written")
    path.parent.mkdir(exist_ok=True)
    path.write_text(LESSON_TEMPLATE.format(title=a.title, today=datetime.now().astimezone().date().isoformat()))
    append_lesson(mod["dir"], lid, a.title, n)
    shown = path.relative_to(ROOT) if ROOT in path.parents else path
    print(f"created {shown} and appended it to {a.module}/module.yaml (status: draft)")
    if mod.get("private"):
        print("this module is local-only (private overlay): no docs to regenerate and nothing to commit to this repo")
    else:
        print("next: write it, run `python scripts/course.py docs`, then commit lesson + yaml + docs together")
    return 0


CURRICULUM_TEMPLATE = """id: {id}
title: {title}
summary: >
  TODO: what this track teaches and who it is for.
audience: "TODO"
level: intermediate        # beginner | intermediate | advanced
status: draft              # draft | active | complete
version: 0.1.0
requires:
  curricula: []            # recommended earlier tracks, e.g. [core]
  modules: []              # recommended earlier modules (global ids)
levels:
  - id: foundations
    title: "Foundations"
    units: []              # add: `- module: some-key` (owned; planned until written) or `- uses: existing-module-id` (reused)
capstones: []
"""


def cmd_new_curriculum(a) -> int:
    cur = curricula_api()
    if not cur.ID_RE.match(a.id) or a.id == cur.CORE_ID:
        raise SystemExit(f"invalid curriculum id {a.id!r} (lowercase letters, digits, hyphens; 'core' is reserved)")
    if curriculum_root(a.id):
        raise SystemExit(f"curriculum {a.id} already exists at {curriculum_root(a.id)}; nothing written")
    if a.dest:
        d = Path(a.dest).expanduser()
        if d.exists() and any(d.iterdir()):
            raise SystemExit(f"{d} is not empty; nothing written")
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitignore").write_text(".DS_Store\n")
        (d / "README.md").write_text(f"# {a.title}\n\nA drillpad curriculum pack. Plug it in with `export DRILLPAD_CURRICULA_PATH={d}` "
                                     "(or add the folder to that colon-separated list).\n")
    elif a.private:
        d = private_modules_dir().parent / "curricula" / a.id
        d.mkdir(parents=True)
    else:
        d = cur.BUNDLED_DIR / a.id
        d.mkdir(parents=True)
    (d / "modules").mkdir(exist_ok=True)
    (d / "curriculum.yaml").write_text(CURRICULUM_TEMPLATE.format(id=a.id, title=json.dumps(a.title)))
    where = "local only" if a.private else "standalone pack" if a.dest else "bundled with the repo"
    print(f"created {d} ({where})")
    print(f"next: edit curriculum.yaml, then `python scripts/course.py new-module KEY --curriculum {a.id} \"Title\"` for each module")
    return 0


def insert_unit(text: str, level_id: str, unit_lines: list[str]) -> str:
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if re.fullmatch(rf"\s*- id: \"?{re.escape(level_id)}\"?\s*", ln)), None)
    if start is None:
        raise SystemExit(f"level {level_id!r} not found in curriculum.yaml")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^  - id:", lines[i]) or (lines[i] and not lines[i].startswith(" ")):
            end = i
            break
    while end > start and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    ui = next((i for i in range(start, end) if re.match(r"^\s+units:", lines[i])), None)
    if ui is None:
        raise SystemExit(f"level {level_id!r} has no `units:` key")
    if re.match(r"^\s+units:\s*\[\]", lines[ui]):
        lines[ui] = re.sub(r"units:\s*\[\]", "units:", lines[ui])
        end = ui + 1
    lines[end:end] = unit_lines
    return "\n".join(lines)


def cmd_new_curriculum_module(a) -> int:
    cur = curricula_api()
    root = curriculum_root(a.curriculum)
    if not root:
        raise SystemExit(f"unknown curriculum {a.curriculum}")
    key = a.id
    if not cur.KEY_RE.match(key):
        raise SystemExit(f"invalid module key {key!r} (lowercase letters, digits, hyphens)")
    mdir = root / "modules" / key
    if mdir.exists():
        raise SystemExit(f"{mdir} already exists; nothing written")
    ypath = root / "curriculum.yaml"
    raw = yaml.safe_load(ypath.read_text()) or {}
    unit = next((u for lv in raw.get("levels") or [] for u in lv.get("units") or [] if u.get("module") == key), None)
    title = a.title or a.stage or (unit or {}).get("title")
    if not title:
        raise SystemExit('usage: new-module KEY --curriculum CID [--level LID] "Title"')
    summary = (unit or {}).get("summary") or "TODO"
    if unit is None:
        levels = raw.get("levels") or []
        if not levels:
            raise SystemExit("the curriculum has no levels; add one to curriculum.yaml first")
        level_id = a.level or str(levels[-1]["id"])
        ypath.write_text(insert_unit(ypath.read_text(), level_id,
                                     [f"      - module: {key}", f"        title: {json.dumps(title)}", f"        summary: {json.dumps(summary)}"]))
    (mdir / "lessons").mkdir(parents=True)
    (mdir / "module.yaml").write_text(f"title: {json.dumps(title)}\nlanguage: systems\ndescription: {json.dumps(summary)}\nlessons: []\n")
    print(f"created {mdir} (global id {a.curriculum}.{key}); {'listed in' if unit is None else 'was already planned in'} curriculum.yaml")
    print(f'next: python scripts/course.py new-lesson {a.curriculum}.{key} <slug> "<title>"')
    return 0


def cmd_new_module(a) -> int:
    if a.curriculum:
        return cmd_new_curriculum_module(a)
    if a.private:
        a.title = a.title or a.stage  # with --private there is no stage, so the first free positional is the title
        if not a.title:
            raise SystemExit('usage: new-module ID --private "Title"')
        d = private_modules_dir() / a.id
        if d.exists() or a.id in load_modules():
            raise SystemExit(f"{a.id} already exists (bundled or private); nothing written")
        (d / "lessons").mkdir(parents=True)
        (d / "module.yaml").write_text(
            f"id: {a.id}\ntitle: {json.dumps(a.title)}\nlanguage: {a.language}\ndescription: {json.dumps('TODO')}\nlessons: []\n")
        print(f"created {d} (local only: it never ships in a public export)")
        print(f'next: `python scripts/course.py new-lesson {a.id} <slug> "<title>"`')
        return 0
    if not a.stage or not a.title:
        raise SystemExit('usage: new-module ID STAGE "Title" (or: new-module ID --private "Title")')
    paths = load_paths()
    if a.stage not in {s["id"] for s in paths["stages"]}:
        raise SystemExit(f"unknown stage {a.stage}; stages: {', '.join(s['id'] for s in paths['stages'])}")
    d = MODULES / a.id
    if d.exists():
        raise SystemExit(f"{d} already exists; nothing written")
    (d / "lessons").mkdir(parents=True)
    (d / "module.yaml").write_text(
        f"id: {a.id}\ntitle: {json.dumps(a.title)}\nlanguage: {a.language}\ndescription: {json.dumps('TODO')}\nlessons: []\n")
    lines = PATHS.read_text().split("\n")
    start = next(i for i, ln in enumerate(lines) if re.match(rf'^\s*- id: "?{re.escape(a.stage)}"?\s*$', ln))
    mi = next(i for i in range(start, len(lines)) if lines[i].strip() == "modules:")
    last = mi
    while last + 1 < len(lines) and re.match(r"^\s+- [\w-]+\s*$", lines[last + 1]):
        last += 1
    lines.insert(last + 1, f"      - {a.id}")
    PATHS.write_text("\n".join(lines))
    print(f"created {d.relative_to(ROOT)} and placed it in stage {a.stage}")
    print(f'next: `python scripts/course.py new-lesson {a.id} <slug> "<title>"`, then `docs`')
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("docs").set_defaults(fn=cmd_docs)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    r = sub.add_parser("report")
    r.add_argument("--stale-days", type=int, default=120)
    r.set_defaults(fn=cmd_report)
    nl = sub.add_parser("new-lesson")
    nl.add_argument("module"), nl.add_argument("slug"), nl.add_argument("title")
    nl.set_defaults(fn=cmd_new_lesson)
    nm = sub.add_parser("new-module")
    nm.add_argument("id"), nm.add_argument("stage", nargs="?"), nm.add_argument("title", nargs="?")
    nm.add_argument("--language", default="systems")
    nm.add_argument("--private", action="store_true", help="create in the private overlay instead of the repo")
    nm.add_argument("--curriculum", help="create the module inside this curriculum instead of the core course")
    nm.add_argument("--level", help="with --curriculum: the level to add a new unit to (default: the last level)")
    nc = sub.add_parser("new-curriculum")
    nc.add_argument("id"), nc.add_argument("title")
    nc.add_argument("--private", action="store_true"), nc.add_argument("--dest")
    nc.set_defaults(fn=cmd_new_curriculum)
    nm.set_defaults(fn=cmd_new_module)
    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
