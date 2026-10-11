"""Every shipped problem must pass its reference solution and fail from the bare starter.

Reference solutions live in tests/solutions/<problem-id>.py and come from the interview-prep
markdown. Deviations from the source are listed in SOURCE_FIXES below.
"""

from pathlib import Path

import pytest

from drillpad.content.loader import PACKS_DIR, load_all
from drillpad.runner import registry

SOLUTIONS_DIR = Path(__file__).parent.parent / "src" / "drillpad" / "content" / "solutions"
SOLUTIONS: dict[str, str] = {p.stem: p.read_text() for ext in ("py", "cpp", "rs") for p in sorted(SOLUTIONS_DIR.glob(f"*.{ext}"))}

# Honest notes on places the source markdown was wrong or imprecise (see the solution files).
SOURCE_FIXES = {
    "write-policies": "source get() evaluated store.read(key) eagerly (dict.get default) even on a "
    "cache hit, defeating the cache; reference now reads the store only on a miss.",
}

ALL = load_all()
PACK_NAMES = {"core-ds", "caching", "concurrency", "ratelimit", "leetcode", "trading", "fintech", "aiinfra", "systems", "cpp", "rust", "ml"}
CATEGORIES = {"leetcode", "systems-impl", "trading", "fintech", "ai-infra", "ml"}
LANGUAGES = {"python", "cpp", "rust"}
FIRM_TAGS = {"ai-infra", "quant-hft", "distsys"}


def test_every_problem_has_a_solution_and_vice_versa():
    assert set(ALL) == set(SOLUTIONS)


def test_packs_layout_and_ids():
    files = sorted(PACKS_DIR.rglob("*.yaml"))
    assert {f.parent.name for f in files} <= PACK_NAMES
    for f in files:
        assert f.stem in ALL, f"file name must equal problem id: {f}"


@pytest.mark.parametrize("pid", sorted(ALL))
def test_metadata(pid):
    p = ALL[pid]
    assert p.id == pid and pid == pid.lower() and " " not in pid and "_" not in pid
    assert 1 <= p.bar_level <= 4
    assert p.target_minutes > 0
    assert p.patterns and p.hints and p.follow_ups and p.statement.strip() and p.starter.strip()
    assert set(p.firm_tags) <= FIRM_TAGS  # may be empty for generic LeetCode-style problems
    assert p.categories and set(p.categories) <= CATEGORIES
    for q in p.anki_queries:
        ok_prep = q.startswith('deck:"Interview Prep*" "Item:') and q.endswith(' - *"')
        ok_lc = q.startswith('deck:"HFT LeetCode 150" "Front:') and q.endswith('"')
        assert ok_prep or ok_lc, q
    visible = [t for t in p.tests if not t.hidden]
    hidden = [t for t in p.tests if t.hidden]
    assert len(visible) >= 2 and len(hidden) >= 1
    assert len({t.name for t in p.tests}) == len(p.tests)


@pytest.mark.parametrize("pid", sorted(ALL))
def test_reference_solution_passes_all_tests(pid):
    p = ALL[pid]
    r = registry.run_problem(SOLUTIONS[pid], p)
    assert not r.compile_error, r.stderr[:600]
    assert not r.timed_out, r.stderr
    assert len(r.results) == len(p.tests), r.stderr
    failed = [(x.name, x.message) for x in r.results if not x.passed]
    assert not failed, failed


@pytest.mark.parametrize("pid", sorted(ALL))
def test_starter_fails_every_test(pid):
    p = ALL[pid]
    r = registry.run_problem(p.starter, p)
    assert not r.compile_error, f"starter must compile: {r.stderr[:600]}"
    assert not r.timed_out, "starter must fail fast, not hang"
    assert len(r.results) == len(p.tests), r.stderr
    passed = [x.name for x in r.results if x.passed]
    assert not passed, f"tests that pass on the bare starter prove nothing: {passed}"


# --- scoring-engine enrichment: edge tags, complexity, extensions ---------------------------------

import re

from drillpad.core.taxonomy import EDGE_TAGS

# Canonical complexity text: "O(...)" optionally followed by one qualifier.
COMPLEXITY_RE = re.compile(r"^O\(.+\)( amortized| expected| worst case)?$")
EXTENSION_KINDS = {"reasoning", "complexity", "design", "code"}


@pytest.mark.parametrize("pid", sorted(ALL))
def test_every_test_has_valid_edge_tags(pid):
    for t in ALL[pid].tests:
        assert t.tags, f"{pid}/{t.name}: needs at least one tag"
        assert set(t.tags) <= set(EDGE_TAGS), f"{pid}/{t.name}: unknown tags {set(t.tags) - set(EDGE_TAGS)}"
        assert len(set(t.tags)) == len(t.tags)


@pytest.mark.parametrize("pid", sorted(ALL))
def test_at_least_three_distinct_tags(pid):
    distinct = {tag for t in ALL[pid].tests for tag in t.tags}
    assert len(distinct) >= 3, f"{pid}: only {sorted(distinct)}"


@pytest.mark.parametrize("pid", sorted(ALL))
def test_complexity_present_and_well_formed(pid):
    cx = ALL[pid].complexity
    assert cx, f"{pid}: complexity required"
    assert len({c.op for c in cx}) == len(cx), "duplicate op names"
    for c in cx:
        assert c.op.strip()
        for s in [c.time, c.space, *c.accepted_time, *c.accepted_space]:
            assert COMPLEXITY_RE.match(s), f"{pid}/{c.op}: bad complexity text {s!r}"


@pytest.mark.parametrize("pid", sorted(ALL))
def test_extensions_present_and_well_formed(pid):
    ext = ALL[pid].extensions
    assert 3 <= len(ext) <= 5, f"{pid}: {len(ext)} extensions"
    for e in ext:
        assert e.q.strip() and e.kind in EXTENSION_KINDS
        assert len(e.key_points) >= 3 and all(k.strip() for k in e.key_points)
    kinds = {e.kind for e in ext}
    assert "complexity" in kinds, f"{pid}: needs a complexity extension"
    assert kinds & {"design"}, f"{pid}: needs a design extension"


def test_follow_ups_preserved_and_enrichment_covers_all():
    assert len(ALL) >= 23
    assert all(p.follow_ups for p in ALL.values())


@pytest.mark.parametrize("pid", sorted(ALL))
def test_walkthrough_fields_present_and_typed(pid):
    p = ALL[pid]
    assert isinstance(p.narration, list) and all(isinstance(s, str) and s.strip() for s in p.narration)
    assert isinstance(p.state_aloud, list) and all(isinstance(s, str) and s.strip() for s in p.state_aloud)
    assert isinstance(p.walkthrough, str)


def test_walkthrough_fields_coverage():
    assert sum(1 for p in ALL.values() if p.narration) >= 23
    assert sum(1 for p in ALL.values() if p.state_aloud) >= 23
    assert sum(1 for p in ALL.values() if p.walkthrough.strip()) >= 23


@pytest.mark.parametrize("pid", sorted(ALL))
def test_language_and_pack_match(pid):
    p = ALL[pid]
    assert p.language in LANGUAGES
    pack = next(f.parent.name for f in PACKS_DIR.rglob(f"{pid}.yaml"))
    if p.language != "python":
        assert pack == p.language, f"{pid}: {p.language} problems live in packs/{p.language}/"
    assert (SOLUTIONS_DIR / f"{pid}{ {'python': '.py', 'cpp': '.cpp', 'rust': '.rs'}[p.language] }").exists()
