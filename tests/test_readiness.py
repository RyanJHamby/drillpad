import pytest

from drillpad.readiness import model as m
from drillpad.readiness.report import bar, render

CFG = m.load_config()
H = CFG.heuristics


def clean(target=20, elapsed=10, hints=0, passed=True, timed=True):
    return m.Solve(passed, hints, elapsed, target, timed)


def test_heuristics_labelled_in_yaml():
    text = m.LEVELS_PATH.read_text()
    assert "INITIAL HEURISTIC" in text
    assert set(CFG.levels) == {"L1", "L2", "L3", "L4"}


def test_level_patterns_cover_pack_and_master_list():
    assert {"amortized-analysis", "array-resize"} <= set(CFG.levels["L1"].weights)
    assert "lru-cache" in CFG.levels["L3"].weights and "memory-model-happens-before" in CFG.levels["L4"].weights


def test_solve_score_components():
    assert m.solve_score(clean(), H) == 1.0
    assert m.solve_score(clean(passed=False), H) == 0.0
    assert m.solve_score(clean(hints=1), H) == pytest.approx(1 - H.hint_penalty)
    assert m.solve_score(clean(elapsed=30), H) < 1.0  # over target
    assert m.solve_score(clean(elapsed=40), H) == pytest.approx(H.time_floor)
    assert m.solve_score(clean(elapsed=400), H) == pytest.approx(H.time_floor)
    assert m.solve_score(clean(hints=10), H) == 0.0


def test_mastery_needs_window_of_timed_solves():
    assert m.pattern_mastery([], H) == 0.0
    assert m.pattern_mastery([clean()], H) == pytest.approx(1 / H.window)
    assert m.pattern_mastery([clean()] * 3, H) == 1.0
    untimed = [clean(timed=False)] * 5
    assert m.pattern_mastery(untimed, H) == 0.0


def test_only_last_three_timed_count_in_time_order():
    from datetime import UTC, datetime
    bad = [m.Solve(False, 0, 5, 20, True, datetime(2026, 1, d, tzinfo=UTC)) for d in (1, 2)]
    good = [m.Solve(True, 0, 5, 20, True, datetime(2026, 2, d, tzinfo=UTC)) for d in (1, 2, 3)]
    assert m.pattern_mastery(good + bad, H) == 1.0  # input order irrelevant


def test_retrievability_blends():
    base = m.pattern_mastery([clean()] * 3, H)
    low = m.pattern_mastery([clean()] * 3, H, retrievability=0.0)
    assert low == pytest.approx(base * (1 - H.retrievability_weight))
    assert m.pattern_mastery([clean()] * 3, H, retrievability=1.0) == 1.0
    assert m.pattern_mastery([clean()] * 3, H, retrievability=7) == 1.0  # clamped


def test_reps_to_mastery():
    assert m.reps_to_mastery([clean()] * 3, H) == 0
    n = m.reps_to_mastery([], H)
    assert 1 <= n <= H.window
    assert m.reps_to_mastery([clean()] * 2, H) <= n


def test_level_readiness_zero_partial_full():
    lvl = CFG.levels["L2"]
    zero = m.level_readiness(lvl, {}, H)
    assert zero.readiness == 0 and not zero.ready and len(zero.gaps) == len(lvl.weights)
    full = {p: [clean()] * 3 for p in lvl.weights}
    r = m.level_readiness(lvl, full, H)
    assert r.readiness == pytest.approx(1.0) and r.ready and r.gaps == [] and r.mastered == r.total
    part = dict(full)
    part.pop("dp-1d-2d")
    p = m.level_readiness(lvl, part, H)
    assert 0 < p.readiness < 1 and [g.pattern for g in p.gaps] == ["dp-1d-2d"]
    assert "1 patterns not yet at mastery" in p.gap_summary


def test_gap_sorted_by_weighted_shortfall():
    lvl = m.Level("X", "x", {"big": 9, "small": 1})
    r = m.level_readiness(lvl, {}, H)
    assert [g.pattern for g in r.gaps] == ["big", "small"]


def test_cpp_track_starts_at_zero_and_report_renders():
    res = m.compute_readiness(CFG, {"two-pointers-sliding-window": [clean()] * 3})
    assert res["cpp"].readiness == 0.0 and res["cpp"].mastered == 0
    assert res["L2"].readiness > 0
    text = render(res)
    assert "cpp" in text and "L1" in text and "initial heuristics" in text and "reps" in text
    assert bar(0.5, 10) == "[#####.....]"
    assert bar(5, 4) == "[####]" and bar(-1, 4) == "[....]"
