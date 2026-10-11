"""Pluggable curricula: named learning tracks that own modules and/or reuse modules defined elsewhere.

A curriculum is a folder containing `curriculum.yaml` and, optionally, `modules/<key>/module.yaml` + `lessons/*.md`:

    id: power-grid-compute
    title: Power Grids & Compute
    summary: ...
    level: intermediate          # beginner | intermediate | advanced (informational)
    status: draft                # draft | active | complete
    requires:
      curricula: [core]          # recommended earlier tracks (informational)
      modules: [reasoning-under-constraints]
    levels:
      - id: foundations
        title: Foundations
        units:
          - module: grid-basics        # a module this curriculum owns (modules/grid-basics/); planned until it exists
            title: How the grid works
            summary: ...
          - uses: queueing-theory      # reuse an existing module by its global id
    capstones:
      - id: ...

Owned modules get the global id `<curriculum-id>.<key>`, so independently authored curricula can never collide.
Curricula load from three kinds of roots (see `roots()`): the bundled content, the private overlay, and any folders listed in
DRILLPAD_CURRICULA_PATH (a root may be a folder of curricula or a single curriculum folder, e.g. a git clone).
The built-in `core` curriculum is synthesized from paths.yaml and is not a folder.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from drillpad.core import paths

BUNDLED_DIR = Path(__file__).resolve().parent.parent / "content" / "curricula"
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
KEY_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LEVELS = ("beginner", "intermediate", "advanced")
STATUSES = ("draft", "active", "complete")
CORE_ID = "core"
log = logging.getLogger(__name__)


@dataclass
class Unit:
    key: str  # module key (owned) or global module id (reused)
    module_id: str  # global module id
    title: str
    summary: str
    owned: bool
    status: str  # ready | planned | missing


@dataclass
class Level:
    id: str
    title: str
    units: list[Unit] = field(default_factory=list)


@dataclass
class Curriculum:
    id: str
    title: str
    summary: str = ""
    audience: str = ""
    level: str = ""
    status: str = "draft"
    version: str = ""
    requires_curricula: list[str] = field(default_factory=list)
    requires_modules: list[str] = field(default_factory=list)
    levels: list[Level] = field(default_factory=list)
    capstones: list[dict] = field(default_factory=list)
    source: str = "bundled"  # bundled | private | external | builtin
    root: Path | None = None

    def units(self) -> list[Unit]:
        return [u for lv in self.levels for u in lv.units]


def roots() -> list[tuple[str, Path]]:
    out = [("bundled", BUNDLED_DIR), ("private", paths.private_dir() / "curricula")]
    out += [("external", Path(p).expanduser()) for p in os.environ.get("DRILLPAD_CURRICULA_PATH", "").split(os.pathsep) if p.strip()]
    return out


def curriculum_dirs(root: Path) -> list[Path]:
    if (root / "curriculum.yaml").exists():
        return [root]
    return sorted(p for p in root.glob("*/") if (p / "curriculum.yaml").exists()) if root.exists() else []


def _str_list(v) -> list[str]:
    return [str(x) for x in v] if isinstance(v, list) else []


def read_curriculum(d: Path, source: str) -> tuple[Curriculum | None, list[str]]:
    """Parse and validate one curriculum folder. Returns (curriculum or None if unusable, problems)."""
    problems: list[str] = []
    try:
        raw = yaml.safe_load((d / "curriculum.yaml").read_text()) or {}
    except (OSError, yaml.YAMLError) as e:
        return None, [f"{d}: unreadable curriculum.yaml: {e}"]
    cid = str(raw.get("id", ""))
    if not ID_RE.match(cid) or cid == CORE_ID:
        return None, [f"{d}: invalid curriculum id {cid!r} (lowercase letters, digits, hyphens; 'core' is reserved)"]
    if source != "external" and d.name != cid:
        problems.append(f"{cid}: folder name {d.name!r} should equal the curriculum id")
    if not str(raw.get("title", "")).strip():
        problems.append(f"{cid}: title is required")
    if raw.get("level") and raw["level"] not in LEVELS:
        problems.append(f"{cid}: level must be one of {LEVELS}")
    if raw.get("status", "draft") not in STATUSES:
        problems.append(f"{cid}: status must be one of {STATUSES}")
    req = raw.get("requires") or {}
    cur = Curriculum(id=cid, title=str(raw.get("title", cid)), summary=str(raw.get("summary", "")).strip(),
                     audience=str(raw.get("audience", "")).strip(), level=str(raw.get("level", "")),
                     status=str(raw.get("status", "draft")), version=str(raw.get("version", "")),
                     requires_curricula=_str_list(req.get("curricula")), requires_modules=_str_list(req.get("modules")),
                     capstones=[c for c in (raw.get("capstones") or []) if isinstance(c, dict)], source=source, root=d)
    seen_levels, seen_modules = set(), set()
    for lv in raw.get("levels") or []:
        lid = str(lv.get("id", ""))
        if not KEY_RE.match(lid) or lid in seen_levels:
            problems.append(f"{cid}: level id {lid!r} is missing, malformed, or duplicated")
            continue
        seen_levels.add(lid)
        level = Level(id=lid, title=str(lv.get("title", lid)))
        for u in lv.get("units") or []:
            unit = _read_unit(cid, d, u, problems)
            if unit is None:
                continue
            if unit.module_id in seen_modules:
                problems.append(f"{cid}: module {unit.module_id} appears twice")
                continue
            seen_modules.add(unit.module_id)
            level.units.append(unit)
        cur.levels.append(level)
    return cur, problems


def _read_unit(cid: str, d: Path, u: dict, problems: list[str]) -> Unit | None:
    if not isinstance(u, dict) or ("module" in u) == ("uses" in u):
        problems.append(f"{cid}: each unit needs exactly one of `module` (owned) or `uses` (reused): {u!r}")
        return None
    if "uses" in u:
        gid = str(u["uses"])
        return Unit(key=gid, module_id=gid, title=str(u.get("title", "")), summary=str(u.get("summary", "")).strip(),
                    owned=False, status="missing")  # resolved against known modules later
    key = str(u["module"])
    if not KEY_RE.match(key):
        problems.append(f"{cid}: bad module key {key!r}")
        return None
    mdir = d / "modules" / key
    ready = (mdir / "module.yaml").exists()
    title = str(u.get("title", ""))
    if ready and not title:
        try:
            title = str((yaml.safe_load((mdir / "module.yaml").read_text()) or {}).get("title", key))
        except (OSError, yaml.YAMLError):
            title = key
    if not ready and not title:
        problems.append(f"{cid}: planned module {key!r} needs a title")
        return None
    return Unit(key=key, module_id=f"{cid}.{key}", title=title or key, summary=str(u.get("summary", "")).strip(),
                owned=True, status="ready" if ready else "planned")


def load_curricula(known_modules: set[str], sources: set[str] | None = None) -> tuple[dict[str, Curriculum], list[str]]:
    """Curricula from every root (or only the given source kinds). `known_modules` are the global ids that exist outside curricula."""
    found: dict[str, Curriculum] = {}
    problems: list[str] = []
    for source, root in roots():
        if sources and source not in sources:
            continue
        for d in curriculum_dirs(root):
            c, probs = read_curriculum(d, source)
            problems += probs
            if c is None:
                continue
            if c.id in found:
                problems.append(f"{c.id}: duplicate curriculum id (from {d}); the earlier one wins")
                continue
            found[c.id] = c
    owned = {u.module_id for c in found.values() for u in c.units() if u.owned and u.status == "ready"}
    everything = set(known_modules) | owned
    for c in found.values():
        for u in c.units():
            if not u.owned:
                u.status = "ready" if u.module_id in everything else "missing"
                if u.status == "missing":
                    problems.append(f"{c.id}: reused module {u.module_id!r} does not exist")
    return found, problems


def owned_modules(c: Curriculum) -> dict[str, Path]:
    """Global module id -> module folder, for the modules this curriculum owns and has written."""
    return {u.module_id: c.root / "modules" / u.key for u in c.units() if u.owned and u.status == "ready"}


def core_from_paths(paths_cfg: dict, module_ids: set[str]) -> Curriculum:
    """The built-in core curriculum: the stages in paths.yaml, plus an 'unsorted' level for modules not placed in any stage."""
    core = Curriculum(id=CORE_ID, title="Core Systems Engineering", status="active", source="builtin",
                      summary="The foundational course: hardware and concurrency through distributed systems, operating production "
                              "systems, AI infrastructure, and staff-level skills.")
    placed: set[str] = set()
    for st in paths_cfg.get("stages") or []:
        level = Level(id=str(st["id"]), title=str(st.get("title", st["id"])))
        for m in st.get("modules") or []:
            if m in module_ids:
                level.units.append(Unit(key=m, module_id=m, title="", summary="", owned=False, status="ready"))
                placed.add(m)
        core.levels.append(level)
    rest = sorted(m for m in module_ids if m not in placed)
    if rest:
        core.levels.append(Level(id="unsorted", title="Unsorted",
                                 units=[Unit(key=m, module_id=m, title="", summary="", owned=False, status="ready") for m in rest]))
    return core
