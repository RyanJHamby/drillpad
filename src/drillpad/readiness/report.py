"""Plain-text readiness report with ASCII bars."""
from __future__ import annotations

from drillpad.readiness.model import LevelReadiness


def bar(frac: float, width: int = 20) -> str:
    frac = min(1.0, max(0.0, frac))
    filled = round(frac * width)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def render(readiness: dict[str, LevelReadiness], max_gaps: int = 5) -> str:
    lines = ["Readiness by bar level (thresholds are initial heuristics; see readiness/levels.yaml)", ""]
    for key, r in readiness.items():
        status = "READY" if r.ready else "not ready"
        lines.append(f"{key:<4} {bar(r.readiness)} {r.readiness * 100:5.1f}%  {status}  - {r.name}")
        lines.append(f"     {r.mastered}/{r.total} patterns at mastery; {r.gap_summary}")
        for g in r.gaps[:max_gaps]:
            lines.append(f"       - {g.pattern:<34} {bar(g.mastery, 10)} {g.mastery * 100:3.0f}%  ~{g.reps_needed} reps")
        if len(r.gaps) > max_gaps:
            lines.append(f"       ... and {len(r.gaps) - max_gaps} more")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
