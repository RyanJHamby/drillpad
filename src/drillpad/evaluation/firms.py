"""Firm profiles (content/firms/*.yaml) with a built-in generic fallback."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from drillpad.core import paths
from drillpad.core.taxonomy import DIMENSIONS

FIRMS_DIR = Path(__file__).resolve().parent.parent / "content" / "firms"

DEFAULT_WEIGHTS = {"correctness": 30, "edge_cases": 15, "complexity": 15, "pace": 15,
                   "communication": 10, "extensions": 10, "quality": 5}


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    weights: dict[str, int]
    pass_score: int
    floors: dict[str, float]
    pace_by_level: dict[int, int] = field(default_factory=dict)
    approach_by_minute: int = 7
    first_code_by_minute: int = 12
    family: str = ""
    earns: list[str] = field(default_factory=list)
    loses: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    problem_ids: list[str] = field(default_factory=list)
    missing_problems: list = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    canonical_topics: list[str] = field(default_factory=list)
    format_confidence: str = ""
    rubric_confidence: str = "inferred"  # weights/bar/pace: 'inferred' unless the firm published them


GENERIC = Profile(
    id="generic", name="Generic (default rubric)", weights=DEFAULT_WEIGHTS, pass_score=80,
    floors={"correctness": 0.9, "complexity": 0.7},
)


def _from_yaml(d: dict) -> Profile:
    w = d["weights"]
    assert set(w) == set(DIMENSIONS) and sum(w.values()) == 100, f"bad weights in {d.get('id')}"
    bar = d.get("bar", {})
    pace = d.get("pace", {})
    return Profile(
        id=d["id"], name=d.get("name", d["id"]), weights=w, pass_score=int(bar.get("pass_score", 80)),
        floors={k: float(v) for k, v in (bar.get("floors") or {}).items()},
        pace_by_level={int(k): int(v) for k, v in (pace.get("target_minutes_by_level") or {}).items()},
        approach_by_minute=int(pace.get("approach_by_minute", 7)),
        first_code_by_minute=int(pace.get("first_code_by_minute", 12)),
        family=d.get("family", ""), earns=d.get("what_earns_points", []), loses=d.get("what_loses_points", []),
        red_flags=d.get("red_flags", []), problem_ids=d.get("problem_ids", []),
        missing_problems=d.get("missing_problems", []), tags=d.get("tags", []),
        canonical_topics=d.get("canonical_topics", []),
        format_confidence=d.get("format_confidence", d.get("confidence", "")),
        rubric_confidence="documented" if all(d.get(k) == "documented" for k in ("weights_confidence", "bar_confidence", "pace_confidence")) else "inferred",
    )


def load_profiles(path: Path = FIRMS_DIR) -> dict[str, Profile]:
    """Bundled profiles, plus (for the default path only) private ones from <data dir>/private/firms, which win on a clash."""
    out = {GENERIC.id: GENERIC}
    folders = [path, paths.private_dir() / "firms"] if path == FIRMS_DIR else [path]
    for folder in folders:
        if folder.exists():
            for f in sorted(folder.glob("*.yaml")):
                p = _from_yaml(yaml.safe_load(f.read_text()))
                out[p.id] = p
    return out
