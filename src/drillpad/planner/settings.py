"""User-adjustable study knobs. Plain data so the UI, API and tests share one shape."""

import json
from dataclasses import asdict, dataclass, field

CATEGORIES = ["leetcode", "systems-impl", "trading", "fintech", "ai-infra", "ml"]
LANGUAGES = ["python", "cpp", "rust"]
LANGUAGE_LABELS = {"python": "Python (default)", "cpp": "C++", "rust": "Rust"}
CATEGORY_LABELS = {"leetcode": "LeetCode-style", "systems-impl": "Design / systems implementation",
                   "trading": "Trading / hedge fund", "fintech": "Fintech", "ai-infra": "AI labs / infra", "ml": "ML / PyTorch basics"}


@dataclass
class FirmSlot:
    id: str
    date: str | None = None  # ISO date of the screen/onsite; None = no date
    weight: int = 70  # 0-100 how much this firm matters right now
    active: bool = True
    stage: str = "screen"


@dataclass
class Settings:
    firms: list[FirmSlot] = field(default_factory=list)
    categories: dict[str, int] = field(default_factory=lambda: dict.fromkeys(CATEGORIES, 50))
    firm_vs_pattern: int = 50  # 0 = pure category/pattern work, 100 = pure firm-specific
    chase_gaps: int = 50  # 0 = steady coverage, 100 = hammer weak spots and stale reviews
    session_minutes: int = 60
    urgency: bool = True  # auto-ramp a firm's weight as its date approaches
    interleave: bool = True  # avoid back-to-back problems on the same pattern
    use_anki: bool = True  # boost problems whose Anki card is due
    languages: dict[str, int] = field(default_factory=lambda: {"python": 100, "cpp": 40, "rust": 30})  # exposure mix


def _clamp(v, lo=0, hi=100):
    return max(lo, min(hi, int(v)))


def from_dict(d: dict | None) -> Settings:
    base = Settings()
    if not d:
        return base
    base.firms = [FirmSlot(id=str(f["id"]), date=f.get("date") or None, weight=_clamp(f.get("weight", 70)),
                           active=bool(f.get("active", True)), stage=str(f.get("stage", "screen")))
                  for f in d.get("firms", [])]
    cats = d.get("categories") or {}
    base.categories = {c: _clamp(cats.get(c, 50)) for c in CATEGORIES}
    base.firm_vs_pattern = _clamp(d.get("firm_vs_pattern", 50))
    base.chase_gaps = _clamp(d.get("chase_gaps", 50))
    base.session_minutes = _clamp(d.get("session_minutes", 60), 15, 240)
    langs = d.get("languages") or {}
    base.languages = {lg: _clamp(langs.get(lg, base.languages[lg])) for lg in LANGUAGES}
    for k in ("urgency", "interleave", "use_anki"):
        setattr(base, k, bool(d.get(k, getattr(base, k))))
    return base


def load(conn) -> Settings:
    row = conn.execute("SELECT settings_json FROM plan_settings WHERE id = 1").fetchone()
    return from_dict(json.loads(row["settings_json"])) if row else Settings()


def save(conn, s: Settings) -> None:
    conn.execute(
        "INSERT INTO plan_settings(id, settings_json) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET settings_json = excluded.settings_json, "
        "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')", (json.dumps(asdict(s)),))
    conn.commit()


def _cats(target: str, other: int = 15) -> dict[str, int]:
    return {c: (100 if c == target else other) for c in CATEGORIES}


# Presets are partial updates over current settings.
PRESETS = {
    "firm-sprint": {"label": "Firm sprint (screen soon)", "apply": {"firm_vs_pattern": 85, "chase_gaps": 60, "urgency": True}},
    "balanced": {"label": "Balanced", "apply": {"firm_vs_pattern": 50, "chase_gaps": 50}},
    "foundations": {"label": "Foundations (pattern-first)", "apply": {"firm_vs_pattern": 10, "chase_gaps": 40}},
    "weakness-blitz": {"label": "Weakness blitz", "apply": {"chase_gaps": 95}},
    "leetcode-style": {"label": "LeetCode-style", "apply": {"firm_vs_pattern": 20, "categories": _cats("leetcode")}},
    "design-style": {"label": "Design / systems", "apply": {"firm_vs_pattern": 20, "categories": _cats("systems-impl")}},
    "trading-style": {"label": "Trading / hedge fund", "apply": {"firm_vs_pattern": 20, "categories": _cats("trading")}},
    "fintech-style": {"label": "Fintech", "apply": {"firm_vs_pattern": 20, "categories": _cats("fintech")}},
    "ai-lab-style": {"label": "AI labs / infra", "apply": {"firm_vs_pattern": 20, "categories": _cats("ai-infra")}},
}


def apply_preset(s: Settings, preset_id: str) -> Settings:
    d = asdict(s)
    d.update(PRESETS[preset_id]["apply"])
    return from_dict(d)
