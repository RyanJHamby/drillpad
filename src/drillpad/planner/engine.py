"""Study-queue engine. Every pick carries plain-language reasons so the knobs are inspectable.

score = w_base*(p*FIRM + (1-p)*CATEGORY) + w_need*NEED + w_weak*WEAK
  p = firm_vs_pattern/100;  g = chase_gaps/100
  w_base = 0.6-0.3g,  w_need = 0.3+0.2g,  w_weak = 0.1+0.1g      (sum = 1)
FIRM     best over active firms of relevance * weight * urgency (urgency ramps up to 3x over the last 14 days)
CATEGORY highest weight among the problem's categories
NEED     below-bar gap, or staleness of a previously passed problem (+ Anki due)
WEAK     overlap with your high first-run-miss edge-case tags
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from drillpad.core.models import Problem
from drillpad.evaluation.engine import apply_profile
from drillpad.evaluation.firms import Profile
from drillpad.planner.settings import CATEGORIES, Settings

FAMILY_CATS = {
    "quant": ["trading", "leetcode", "systems-impl"],
    "ai-lab": ["ai-infra", "systems-impl", "leetcode"],
    "fintech": ["fintech", "systems-impl", "leetcode"],
    "infra": ["systems-impl", "ai-infra", "leetcode"],
}
FAMILY_FORMAT = {"ai-lab": "progressive-60", "quant": "timed-45", "fintech": "timed-45", "infra": "timed-45"}
BAR = 80  # generic pass score used for need/gap


@dataclass
class Pick:
    problem_id: str
    title: str
    minutes: int
    score: float
    level: int
    categories: list[str]
    reasons: list[str] = field(default_factory=list)
    forced: bool = False


def srs_need(sc: dict) -> tuple[float, str]:
    """Need from an FSRS recall estimate. Overdue reviews outrank never-attempted problems (need 1.0)."""
    r = sc["retrievability"]
    need = min(1.15, max(0.0, (0.95 - r) / 0.35) + (0.15 if sc["due_now"] else 0.0))
    why = f"Due for review: est. recall {r:.0%}, {sc['days_since']:.0f}d since last review" if sc["due_now"] else ""
    return need, why


def derive_categories(p: Problem) -> list[str]:
    if p.categories:
        return p.categories
    out = []
    for t, c in (("quant-hft", "trading"), ("ai-infra", "ai-infra"), ("distsys", "systems-impl")):
        if t in p.firm_tags and c not in out:
            out.append(c)
    return out or ["leetcode"]


def firm_relevance(p: Problem, prof: Profile) -> float:
    if p.id in prof.problem_ids:
        return 1.0
    cats = FAMILY_CATS.get(prof.family, [])
    pc = derive_categories(p)
    rel = 0.0
    for i, c in enumerate(cats):
        if c in pc:
            rel = max(rel, 0.5 if i == 0 else 0.35)
    if set(prof.canonical_topics) & set(p.patterns):
        rel += 0.2
    return min(1.0, rel)


def days_until(d: str | None, today: date) -> int | None:
    return (date.fromisoformat(d) - today).days if d else None


def urgency_factor(days: int | None, on: bool) -> float:
    if not on or days is None:
        return 1.0
    return 1 + 2 * max(0.0, (14 - days) / 14)


def _weights(g: float) -> tuple[float, float, float]:
    return 0.6 - 0.3 * g, 0.3 + 0.2 * g, 0.1 + 0.1 * g


def build(
    s: Settings, problems: dict[str, Problem], profiles: dict[str, Profile], latest_evals: dict[str, dict],
    last_attempt: dict[str, datetime], edge_miss: dict[str, float], anki_due: set[str],
    forced_recall: dict[str, int], now: datetime | None = None, minutes: int | None = None,
    srs_snapshot: dict | None = None,
) -> dict:
    now = now or datetime.now(UTC)
    srs_snapshot = srs_snapshot or {}
    today = now.date()
    p_ = s.firm_vs_pattern / 100
    g = s.chase_gaps / 100
    w_base, w_need, w_weak = _weights(g)
    budget = minutes or s.session_minutes

    active = []
    for f in s.firms:
        prof = profiles.get(f.id)
        d = days_until(f.date, today)
        if not f.active or not prof or (d is not None and d < 0):
            continue
        active.append((f, prof, d, urgency_factor(d, s.urgency)))

    generic = profiles["generic"]
    cand: list[Pick] = []
    for p in problems.values():
        cats = derive_categories(p)
        # FIRM
        best_f, best_why = 0.0, ""
        for f, prof, d, urg in active:
            rel = firm_relevance(p, prof)
            val = rel * f.weight / 100 * urg
            if val > best_f:
                when = f"screen in {d}d" if d is not None else "no date set"
                best_f, best_why = val, f"{prof.name} ({when}): {'in its problem list' if p.id in prof.problem_ids else 'matches its style'}"
        F = min(1.0, best_f)
        # CATEGORY
        C = max((s.categories.get(c, 0) for c in cats), default=0) / 100
        # NEED
        ev = latest_evals.get(p.id)
        la = last_attempt.get(p.id)
        why_need = ""
        if ev:
            total = apply_profile(ev["fr"], generic).total
            gap = max(0.0, (BAR - total) / BAR)
            if total >= BAR:
                sc = srs_snapshot.get(p.id)
                if sc:  # FSRS recall estimate: due once it falls under the retention target
                    need, why_need = srs_need(sc)
                else:
                    interval = 7 + 14 * min(1.0, (total - BAR) / 20)
                    days_since = (now - (la or now)).total_seconds() / 86400
                    due = min(1.0, days_since / interval)
                    need = due * 0.8
                    why_need = f"Passed ({total:.0f}) {days_since:.0f}d ago; review due at ~{interval:.0f}d" if due >= 0.5 else ""
            else:
                need = gap
                why_need = f"Last score {total:.0f} (bar {BAR})"
        else:
            sc = srs_snapshot.get(p.id)  # passed (and reviewed) without ever pressing Score
            if sc:
                need, why_need = srs_need(sc)
            else:
                need = 1.0
                why_need = "Not attempted yet"
        anki = s.use_anki and p.id in anki_due
        if anki:
            need = min(1.0, need + 0.2)
        # WEAK
        tags = {t for tc in p.tests for t in tc.tags}
        wk = sum(edge_miss.get(t, 0) for t in tags) / len(tags) if tags else 0.0
        weak_tags = sorted((t for t in tags if edge_miss.get(t, 0) >= 0.3), key=lambda t: -edge_miss[t])[:3]

        parts = {"firm": w_base * p_ * F, "category": w_base * (1 - p_) * C, "need": w_need * need, "weak": w_weak * wk}
        score = sum(parts.values()) * (0.25 + 0.75 * s.languages.get(p.language, 100) / 100)  # language exposure knob
        why = {
            "firm": best_why, "need": why_need or None,
            "category": "Category focus: " + ", ".join(f"{c} {s.categories.get(c, 0)}" for c in cats),
            "weak": ("Hits your weak edge tags: " + ", ".join(weak_tags)) if weak_tags else None,
        }
        order = ["firm", "need", "weak", "category"]  # lead with whatever discriminates, not the constant baseline
        reasons = [why[k] for k in order if parts[k] > 0.01 and why.get(k)]
        if anki:
            reasons.append("Anki card is due")
        if p.language != "python":
            reasons.append(f"{ {'cpp': 'C++', 'rust': 'Rust'}[p.language] } exposure (weight {s.languages.get(p.language, 100)})")
        pick = Pick(p.id, p.title, p.target_minutes, round(score, 3), p.bar_level, cats, reasons[:4])
        if p.id in forced_recall:
            pick.forced, pick.score = True, 2.0
            pick.reasons.insert(0, f"You opened the solution {forced_recall[p.id]}d ago: retry from memory")
        cand.append(pick)

    # greedy fill with interleaving
    picks: list[Pick] = []
    left = budget
    pool = sorted(cand, key=lambda x: -x.score)
    while pool and len(picks) < 8:
        eff = []
        for c in pool:
            f = 1.0
            if s.interleave and picks:
                last = picks[-1]
                if set(problems[c.problem_id].patterns) & set(problems[last.problem_id].patterns):
                    f *= 0.8
                if c.categories[:1] == last.categories[:1]:
                    f *= 0.92
            eff.append((c.score * f, c))
        eff.sort(key=lambda x: -x[0])
        chosen = next((c for sc, c in eff if c.minutes <= left or not picks), None)
        if not chosen or (picks and chosen.score <= 0.05):
            break
        picks.append(chosen)
        pool.remove(chosen)
        left -= chosen.minutes
        if left <= 0:
            break

    # firm cards + category status
    firm_cards = []
    for f, prof, d, urg in active:
        firm_cards.append({"id": f.id, "name": prof.name, "days": d, "weight": f.weight, "urgency": round(urg, 2),
                           "effective": round(min(1.0, f.weight / 100 * urg), 2), "family": prof.family})
    cat_status = []
    for c in CATEGORIES:
        ids = [p.id for p in problems.values() if c in derive_categories(p)]
        passed = sum(1 for i in ids if i in latest_evals and apply_profile(latest_evals[i]["fr"], generic).total >= BAR)
        attempted = sum(1 for i in ids if i in latest_evals)
        cat_status.append({"id": c, "problems": len(ids), "attempted": attempted, "passing": passed})

    mock = None
    soon = sorted((x for x in active if x[2] is not None and x[2] <= 3), key=lambda x: x[2])
    if soon:
        f, prof, d, _ = soon[0]
        mock = {"firm": prof.name, "days": d, "format": FAMILY_FORMAT.get(prof.family, "timed-45"),
                "why": f"{prof.name} is {d} day(s) away: run a timed mock under its format instead of untimed practice."}

    due_reviews = sorted(
        ({"problem_id": pid, "title": problems[pid].title, "recall": v["retrievability"]}
         for pid, v in srs_snapshot.items() if v["due_now"] and pid in problems), key=lambda x: x["recall"])
    return {
        "due_reviews": due_reviews,
        "picks": [pk.__dict__ for pk in picks], "planned_minutes": sum(pk.minutes for pk in picks), "budget": budget,
        "firms": firm_cards, "categories": cat_status, "mock": mock,
        "weights": {"base": round(w_base, 2), "need": round(w_need, 2), "weak": round(w_weak, 2)},
    }
