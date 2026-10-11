"""Readiness by bar level: pattern mastery -> level readiness % -> gap list.

Pure logic. All thresholds are INITIAL HEURISTICS and live in readiness/levels.yaml (`heuristics:`);
nothing here has hidden defaults. Recalibrate from real results.

Pattern mastery:
  per solve  = max(0, 1 - hint_penalty*hints) * time_factor      (0 if not passed)
  time_factor = 1 at/under target_minutes, linear down to time_floor at target*overrun_limit
  solve part = sum(last `window` TIMED solve scores) / window     (fewer solves => lower; no solves => 0)
  mastery    = solve part, or (1-w)*solve part + w*retrievability when Anki retrievability (0-1) is given
Level readiness = weighted mean over required patterns of min(1, mastery / mastery_threshold).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

LEVELS_PATH = Path(__file__).with_name("levels.yaml")


@dataclass(frozen=True)
class Heuristics:
    mastery_threshold: float
    level_ready_threshold: float
    window: int
    hint_penalty: float
    overrun_limit: float
    time_floor: float
    retrievability_weight: float
    rep_score: float


@dataclass(frozen=True)
class Level:
    key: str
    name: str
    weights: dict[str, float]  # raw weights; normalised in readiness math


@dataclass(frozen=True)
class Config:
    heuristics: Heuristics
    levels: dict[str, Level]
    tracks: dict[str, Level]


@dataclass(frozen=True)
class Solve:
    """One attempt at a problem exercising a pattern. Only timed solves count toward mastery."""
    passed: bool
    hints_used: int
    elapsed_min: float
    target_min: float
    timed: bool = True
    at: datetime | None = None  # used only to order solves; newest are the "last 3"


@dataclass(frozen=True)
class Gap:
    pattern: str
    mastery: float
    weight: float  # normalised within the level
    reps_needed: int  # estimated additional clean timed reps


@dataclass(frozen=True)
class LevelReadiness:
    key: str
    name: str
    readiness: float  # 0..1
    ready: bool
    mastered: int
    total: int
    gaps: list[Gap]

    @property
    def gap_summary(self) -> str:
        reps = sum(g.reps_needed for g in self.gaps)
        return f"{len(self.gaps)} patterns not yet at mastery, ~{reps} reps"


def load_config(path: Path = LEVELS_PATH) -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    h = Heuristics(**raw["heuristics"])
    mk = lambda k, d: Level(k, d["name"], {p: float(w) for p, w in d["patterns"].items()})
    return Config(
        h,
        {k: mk(k, d) for k, d in raw["levels"].items()},
        {k: mk(k, d) for k, d in raw.get("tracks", {}).items()},
    )


def solve_score(s: Solve, h: Heuristics) -> float:
    if not s.passed:
        return 0.0
    base = max(0.0, 1.0 - h.hint_penalty * s.hints_used)
    if s.elapsed_min <= s.target_min or s.target_min <= 0:
        tf = 1.0
    else:
        frac = min(1.0, (s.elapsed_min - s.target_min) / (s.target_min * (h.overrun_limit - 1)))
        tf = 1.0 - frac * (1.0 - h.time_floor)
    return base * tf


def _recent_scores(solves: list[Solve], h: Heuristics) -> list[float]:
    timed = [s for s in solves if s.timed]
    if any(s.at for s in timed):  # stable: undated solves sort oldest
        timed.sort(key=lambda s: (s.at is not None, s.at.timestamp() if s.at else 0.0))
    return [solve_score(s, h) for s in timed[-h.window:]]


def pattern_mastery(solves: list[Solve], h: Heuristics, retrievability: float | None = None) -> float:
    solve_part = sum(_recent_scores(solves, h)) / h.window
    if retrievability is None:
        return solve_part
    r = min(1.0, max(0.0, retrievability))
    return (1 - h.retrievability_weight) * solve_part + h.retrievability_weight * r


def reps_to_mastery(solves: list[Solve], h: Heuristics, retrievability: float | None = None) -> int:
    """Clean timed reps (each scoring h.rep_score) until mastery >= threshold; capped at the window size."""
    scores = _recent_scores(solves, h)
    r = None if retrievability is None else min(1.0, max(0.0, retrievability))
    for n in range(h.window + 1):
        solve_part = sum(scores[-(h.window - n):] if h.window - n > 0 else []) + n * h.rep_score
        solve_part /= h.window
        m = solve_part if r is None else (1 - h.retrievability_weight) * solve_part + h.retrievability_weight * r
        if m >= h.mastery_threshold:
            return n
    return h.window


def level_readiness(
    level: Level,
    solves_by_pattern: dict[str, list[Solve]],
    h: Heuristics,
    retrievability: dict[str, float] | None = None,
) -> LevelReadiness:
    retrievability = retrievability or {}
    total_w = sum(level.weights.values())
    acc, gaps, mastered = 0.0, [], 0
    for pat, w in level.weights.items():
        solves = solves_by_pattern.get(pat, [])
        r = retrievability.get(pat)
        m = pattern_mastery(solves, h, r)
        acc += (w / total_w) * min(1.0, m / h.mastery_threshold)
        if m >= h.mastery_threshold:
            mastered += 1
        else:
            gaps.append(Gap(pat, m, w / total_w, reps_to_mastery(solves, h, r)))
    gaps.sort(key=lambda g: (-(g.weight * (h.mastery_threshold - g.mastery)), g.pattern))
    return LevelReadiness(level.key, level.name, acc, acc >= h.level_ready_threshold, mastered, len(level.weights), gaps)


def compute_readiness(
    cfg: Config,
    solves_by_pattern: dict[str, list[Solve]],
    retrievability: dict[str, float] | None = None,
) -> dict[str, LevelReadiness]:
    """Levels L1-L4 plus language tracks (keyed by track name), all in one dict."""
    out = {k: level_readiness(lv, solves_by_pattern, cfg.heuristics, retrievability) for k, lv in cfg.levels.items()}
    for k, lv in cfg.tracks.items():
        out[k] = level_readiness(lv, solves_by_pattern, cfg.heuristics, retrievability)
    return out

