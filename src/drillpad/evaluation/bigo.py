"""Normalise and compare big-O answers. Core must match; a missing qualifier (amortized/expected) costs credit."""

import re

_QUALS = ("amortized", "expected", "worst case", "average")


def parse(s: str) -> tuple[str, str]:
    t = s.lower().replace("²", "^2").replace("³", "^3").replace("·", "*").replace("θ", "o").replace("θ", "o")
    qual = next((q for q in _QUALS if q in t), "")
    for q in _QUALS:
        t = t.replace(q, "")
    t = re.sub(r"\b(big|oh|theta)\b", "o", t)
    t = t.replace("o(", "(", 1) if re.match(r"\s*o\s*\(", t) else t
    core = re.sub(r"[\s()*,]", "", t)
    core = core.replace("log2n", "logn")
    return core, qual


def score(answer: str, canonical: str, accepted: list[str] | None = None) -> float:
    """1.0 exact; 0.7 right core but omits a qualifier the canonical answer carries; 0 otherwise."""
    if not answer or not answer.strip():
        return 0.0
    a_core, a_q = parse(answer)
    best = 0.0
    for cand in [canonical, *(accepted or [])]:
        c_core, c_q = parse(cand)
        if a_core != c_core:
            continue
        best = max(best, 1.0 if (not c_q or a_q == c_q or cand != canonical) else 0.7)
    return best
