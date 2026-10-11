"""Weakness model: recency-weighted failure rate per (category, tag), plus queue boosts.

Score definition (per category/tag):
    score = (sum_w(fail events * severity/3) + seed_pseudo) / (sum_w(exposures) + prior)
where w = 0.5 ** (age_days / half_life_days).  Exposure = a finished attempt that exercised the tag:
for category "pattern" the attempt's problem must list the tag in `patterns`; for every other
category every finished attempt counts (a language/communication issue can show up anywhere).
`prior` is a smoothing pseudo-count so one early failure is not a 100% failure rate.
All numbers here are initial heuristics, tunable via WeaknessConfig.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from drillpad.core.models import Problem

SEEDS_PATH = Path(__file__).resolve().parent.parent / "content" / "weaknesses.yaml"
CATEGORIES = ("pattern", "language", "algorithm", "problem", "communication")


@dataclass(frozen=True)
class WeaknessConfig:
    half_life_days: float = 14.0
    prior: float = 1.0  # smoothing pseudo-exposure (initial heuristic)
    seed_pseudo_failures: float = 1.0  # extra failure mass for a CONFIRMED seed, scaled by severity/3
    max_boost: float = 1.0  # a score of 1.0 multiplies priority by (1 + max_boost)


DEFAULT_CONFIG = WeaknessConfig()


@dataclass(frozen=True)
class Seed:
    category: str
    tag: str
    severity: int
    status: str
    evidence: str
    description: str
    source: str

    @property
    def confirmed(self) -> bool:
        return self.status == "confirmed"


@dataclass(frozen=True)
class TagScore:
    category: str
    tag: str
    score: float
    failure_weight: float
    exposure_weight: float


def load_seeds(path: Path = SEEDS_PATH) -> list[Seed]:
    raw = yaml.safe_load(Path(path).read_text())["seeds"]
    seeds = [Seed(**d) for d in raw]
    for s in seeds:
        if s.category not in CATEGORIES:
            raise ValueError(f"unknown weakness category {s.category!r}")
        if not 1 <= s.severity <= 3:
            raise ValueError(f"severity out of range for {s.tag}")
    return seeds


def record_event(
    conn: sqlite3.Connection, attempt_id: int, category: str, tag: str, severity: int = 1,
    created_at: str | None = None,
) -> None:
    if category not in CATEGORIES:
        raise ValueError(f"unknown weakness category {category!r}")
    if created_at is None:
        conn.execute(
            "INSERT INTO weakness_events(attempt_id, category, tag, severity) VALUES (?,?,?,?)",
            (attempt_id, category, tag, severity),
        )
    else:
        conn.execute(
            "INSERT INTO weakness_events(attempt_id, category, tag, severity, created_at) VALUES (?,?,?,?,?)",
            (attempt_id, category, tag, severity, created_at),
        )
    conn.commit()


def _parse(ts: str) -> datetime:
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))  # noqa: FURB162
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def decay(age_days: float, half_life_days: float) -> float:
    return 0.5 ** (max(age_days, 0.0) / half_life_days)


def weakness_scores(
    conn: sqlite3.Connection,
    problems: dict[str, Problem],
    now: datetime | None = None,
    config: WeaknessConfig = DEFAULT_CONFIG,
    seeds: list[Seed] | None = None,
) -> dict[tuple[str, str], TagScore]:
    now = now or datetime.now(UTC)

    def w(ts: str) -> float:
        return decay((now - _parse(ts)).total_seconds() / 86400, config.half_life_days)

    # Exposures: finished attempts, weighted by recency of finish.
    attempts = conn.execute(
        "SELECT id, problem_id, COALESCE(finished_at, started_at) AS ts FROM attempts WHERE outcome IS NOT NULL"
    ).fetchall()
    exposure: dict[tuple[str, str], float] = {}
    total_exposure = 0.0
    pattern_exposure: dict[str, float] = {}
    for a in attempts:
        wt = w(a["ts"])
        total_exposure += wt
        prob = problems.get(a["problem_id"])
        for pat in prob.patterns if prob else []:
            pattern_exposure[pat] = pattern_exposure.get(pat, 0.0) + wt

    # Failures: one per (attempt, category, tag) -- the max severity -- decayed from event time.
    rows = conn.execute(
        "SELECT attempt_id, category, tag, MAX(severity) AS sev, MAX(created_at) AS ts "
        "FROM weakness_events GROUP BY attempt_id, category, tag"
    ).fetchall()
    fails: dict[tuple[str, str], float] = {}
    for r in rows:
        key = (r["category"], r["tag"])
        fails[key] = fails.get(key, 0.0) + w(r["ts"]) * r["sev"] / 3

    for s in seeds or []:
        if s.confirmed:
            key = (s.category, s.tag)
            fails[key] = fails.get(key, 0.0) + config.seed_pseudo_failures * s.severity / 3
            exposure.setdefault(key, 0.0)

    out: dict[tuple[str, str], TagScore] = {}
    for key in set(fails) | set(exposure):
        cat, tag = key
        exp = pattern_exposure.get(tag, 0.0) if cat == "pattern" else total_exposure
        f = fails.get(key, 0.0)
        # Failure mass without recorded exposure (problem not in packs) still counts as exposure.
        exp = max(exp, f)
        out[key] = TagScore(cat, tag, min(1.0, f / (exp + config.prior)), f, exp)
    return out


def rank_tags(
    scores: dict[tuple[str, str], TagScore], category: str | None = None, limit: int | None = None
) -> list[TagScore]:
    items = [s for s in scores.values() if category in (None, s.category)]
    items.sort(key=lambda s: (-s.score, s.category, s.tag))
    return items[:limit]


def problem_boost(problem: Problem, scores: dict[tuple[str, str], TagScore], config: WeaknessConfig = DEFAULT_CONFIG) -> float:
    """Multiplier >= 1.0: driven by the worst pattern-category score among problem.patterns."""
    worst = max((scores[("pattern", p)].score for p in problem.patterns if ("pattern", p) in scores), default=0.0)
    return 1.0 + config.max_boost * worst


def boost_queue(
    base_priority: dict[str, float],
    problems: dict[str, Problem],
    scores: dict[tuple[str, str], TagScore],
    config: WeaknessConfig = DEFAULT_CONFIG,
) -> list[tuple[str, float]]:
    """Return (problem_id, boosted_priority) sorted high to low; unknown problems keep base priority."""
    out = []
    for pid, base in base_priority.items():
        prob = problems.get(pid)
        out.append((pid, base * (problem_boost(prob, scores, config) if prob else 1.0)))
    out.sort(key=lambda t: (-t[1], t[0]))
    return out

