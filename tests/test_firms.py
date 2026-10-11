"""Validate every firm profile in src/drillpad/content/firms/*.yaml."""

from pathlib import Path

import pytest
import yaml

from drillpad.content.loader import load_all
from drillpad.core.taxonomy import DIMENSIONS

FIRMS_DIR = Path(__file__).parent.parent / "src" / "drillpad" / "content" / "firms"
FILES = sorted(FIRMS_DIR.glob("*.yaml"))
PROBLEMS = load_all()
FAMILIES = {"ai-lab", "quant", "fintech", "infra"}
CONF = {"documented", "reported", "inferred"}
CONF_FIELDS = ["confidence", "format_confidence", "weights_confidence", "bar_confidence", "pace_confidence"]
REQUIRED = [
    "id", "name", "family", "sources", "format", "weights", "bar", "pace", "what_earns_points",
    "what_loses_points", "red_flags", "canonical_topics", "problem_ids", "missing_problems", "tags",
]
REQUIRED_GENERIC = {"generic-ai-lab", "generic-quant", "generic-infra"}


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def test_firms_exist_and_generics_present():
    ids = {p.stem for p in FILES}
    assert REQUIRED_GENERIC <= ids
    assert len(ids) >= len(REQUIRED_GENERIC)  # a public copy ships only the generic profiles


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_firm_profile(path):
    d = _load(path)
    for key in REQUIRED:
        assert key in d, f"missing {key}"
    assert d["id"] == path.stem
    assert d["family"] in FAMILIES
    assert d["sources"], "needs at least one source"

    for f in CONF_FIELDS:
        if f in d:
            assert d[f] in CONF, f"{f}={d[f]}"
    assert d["weights_confidence"] in CONF

    # weights: exact keys, non-negative ints, sum 100
    w = d["weights"]
    assert list(w) == DIMENSIONS or set(w) == set(DIMENSIONS)
    assert all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in w.values())
    assert sum(w.values()) == 100

    # bar
    bar = d["bar"]
    assert isinstance(bar["pass_score"], int) and 0 < bar["pass_score"] <= 100
    assert set(bar["floors"]) <= set(DIMENSIONS)
    for dim, frac in bar["floors"].items():
        assert 0 <= frac <= 1, dim
        assert w[dim] > 0, f"floor on zero-weight dimension {dim}"

    # pace
    pace = d["pace"]
    levels = pace["target_minutes_by_level"]
    assert set(levels) == {1, 2, 3, 4}
    mins = [levels[i] for i in (1, 2, 3, 4)]
    assert all(isinstance(m, int) and m > 0 for m in mins)
    assert mins == sorted(mins)
    assert isinstance(pace["first_code_by_minute"], int)
    assert isinstance(pace["approach_by_minute"], int)
    assert pace["approach_by_minute"] <= pace["first_code_by_minute"]

    # format keys
    for key in ["rounds", "platform", "minutes", "problems_per_round", "language_notes", "ai_assistance_allowed"]:
        assert key in d["format"], f"format.{key}"

    # problems
    for pid in d["problem_ids"]:
        assert pid in PROBLEMS, f"unknown problem id {pid}"
    assert len(set(d["problem_ids"])) == len(d["problem_ids"])
    for m in d["missing_problems"]:
        assert m["problem"] and m["source"]
        assert m["problem"] not in PROBLEMS

    for key in ["what_earns_points", "what_loses_points", "canonical_topics", "tags"]:
        assert d[key], key
        assert all(isinstance(x, str) for x in d[key])
    assert isinstance(d["red_flags"], list)
    assert all(t == t.lower() for t in d["tags"])
