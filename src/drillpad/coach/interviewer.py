"""Text-only AI interviewer.

Rules decide *when* to speak (coach.pace.check, hint ladder, follow-up schedule); the LLM only phrases
what the rules decided and answers candidate questions in persona. The LLM is injected via the LLMClient
Protocol so tests run against a stub with no network. API keys come from the environment or the OS keychain
and are never written to the repo or the DB.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Protocol

from drillpad.anki.scheduler import ease_for
from drillpad.coach.pace import PHASES_45, check, phase_at
from drillpad.core.models import Problem

log = logging.getLogger("drillpad.interviewer")

DIALOGUE_MODEL = "claude-sonnet-5-5"
CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"
KEYRING_SERVICE = "drillpad"
KEYRING_USER = "anthropic_api_key"

# Estimated list prices, USD per million tokens (input, output). Estimates only; verify against current pricing.
# Cache writes are billed at ~1.25x input, cache reads at ~0.1x input.
PRICES_PER_MTOK = {DIALOGUE_MODEL: (2.00, 10.00), CLASSIFIER_MODEL: (1.00, 5.00)}
CACHE_WRITE_MULT, CACHE_READ_MULT = 1.25, 0.10

HINT_LEVELS = ("nudge", "targeted", "partial")
INTERJECTION_COOLDOWN_MIN = 3.0


# ---------------------------------------------------------------- session formats (data)

@dataclass(frozen=True)
class SessionFormat:
    name: str
    total_min: float
    interrupts: bool = True        # rule-based pace interjections
    chat: bool = True              # interviewer replies at all (False = OA-style, silent)
    voice: bool = True             # voice allowed (backend flag only; text mode ignores it)
    follow_up_window: tuple[float, float] | None = None  # (min, max) minutes between injected requirements


FORMATS: dict[str, SessionFormat] = {
    "progressive-60": SessionFormat("progressive-60", 60, follow_up_window=(15, 20)),
    "timed-45": SessionFormat("timed-45", 45),
    "oa": SessionFormat("oa", 90, interrupts=False, chat=False, voice=False),
}


def get_format(name: str) -> SessionFormat:
    if name not in FORMATS:
        raise ValueError(f"unknown session format {name!r}; choose from {sorted(FORMATS)}")
    return FORMATS[name]


# ---------------------------------------------------------------- LLM client

class MissingAPIKeyError(RuntimeError):
    pass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def add(self, o: Usage) -> None:
        for f in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
            setattr(self, f, getattr(self, f) + getattr(o, f))


@dataclass
class LLMReply:
    text: str
    usage: Usage = field(default_factory=Usage)


class LLMClient(Protocol):
    def complete(self, *, model: str, system: list[dict], messages: list[dict], max_tokens: int) -> LLMReply: ...


def estimate_cost_usd(model: str, u: Usage) -> float:
    pin, pout = PRICES_PER_MTOK.get(model, (0.0, 0.0))
    return (u.input_tokens * pin + u.cache_creation_input_tokens * pin * CACHE_WRITE_MULT
            + u.cache_read_input_tokens * pin * CACHE_READ_MULT + u.output_tokens * pout) / 1e6


def resolve_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    try:
        import keyring
        key = (keyring.get_password(KEYRING_SERVICE, KEYRING_USER) or "").strip()
    except Exception:  # noqa: BLE001 - keyring missing/no backend; fall through to the clear error
        key = ""
    if key:
        return key
    raise MissingAPIKeyError(
        "No Anthropic API key found. Set ANTHROPIC_API_KEY, or store one in the OS keychain with: "
        f"python -c \"import keyring; keyring.set_password('{KEYRING_SERVICE}', '{KEYRING_USER}', '<key>')\" "
        "(requires the 'llm' extra: uv sync --extra llm). The key is never stored in the repo or database."
    )


class AnthropicClient:
    """Real LLMClient wrapping the anthropic SDK (messages.create)."""

    def __init__(self, api_key: str | None = None):
        key = api_key or resolve_api_key()
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("anthropic SDK not installed; run: uv sync --extra llm") from e
        self._client = anthropic.Anthropic(api_key=key)

    def complete(self, *, model: str, system: list[dict], messages: list[dict], max_tokens: int) -> LLMReply:
        resp = self._client.messages.create(model=model, max_tokens=max_tokens, system=system, messages=messages)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        u = resp.usage
        return LLMReply(text, Usage(
            input_tokens=u.input_tokens or 0, output_tokens=u.output_tokens or 0,
            cache_creation_input_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
            cache_read_input_tokens=getattr(u, "cache_read_input_tokens", 0) or 0))


# ---------------------------------------------------------------- persistence

class InterviewStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_session(self, problem_id: str, fmt: str) -> int:
        cur = self.conn.execute("INSERT INTO interview_sessions(problem_id, format) VALUES (?, ?)", (problem_id, fmt))
        self.conn.commit()
        return cur.lastrowid

    def add_event(self, sid: int, role: str, kind: str, content: str = "", elapsed_min: float | None = None,
                  meta: dict | None = None) -> None:
        seq = self.conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM interview_events WHERE session_id=?", (sid,)).fetchone()[0]
        self.conn.execute(
            "INSERT INTO interview_events(session_id, seq, role, kind, content, elapsed_min, meta_json) VALUES (?,?,?,?,?,?,?)",
            (sid, seq, role, kind, content, elapsed_min, json.dumps(meta) if meta else None))
        if kind == "hint":
            self.conn.execute("UPDATE interview_sessions SET hints_used = hints_used + 1 WHERE id=?", (sid,))
        self.conn.commit()

    def session(self, sid: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM interview_sessions WHERE id=?", (sid,)).fetchone()

    def events(self, sid: int) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM interview_events WHERE session_id=? ORDER BY seq", (sid,)).fetchall()

    def finish(self, sid: int, usage: dict, cost: float, summary: dict) -> None:
        self.conn.execute(
            "UPDATE interview_sessions SET finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), usage_json=?, est_cost_usd=?, "
            "summary_json=? WHERE id=?", (json.dumps(usage), cost, json.dumps(summary), sid))
        self.conn.commit()


# ---------------------------------------------------------------- prompts

PERSONA = """You are a senior software engineer conducting a live coding interview, in text chat.
Be realistic and brief: one to three plain sentences, no markdown, no bullet lists, no code blocks.
Never write the solution, never paste code, never confirm that a specific approach is "the right answer".
Answer clarification questions about requirements honestly using the problem statement; if the statement
does not say, make a reasonable call and state it. React to what the candidate said or wrote, not to hidden solutions.
Each user message begins with a [state] block (time, phase, code snapshot) and may contain [directives] that were
decided by the session rules. Follow every directive; phrase them naturally in your own words, do not mention
"directives", "rules", or "the system". If there is no candidate message and no directive, reply with exactly: ...
Hint directives specify a level: nudge = a guiding question only; targeted = point at the specific idea or bug area
without naming the full fix; partial = describe one concrete step but still leave the rest to the candidate."""

CLASSIFIER_SYSTEM = ("Classify the candidate's message in a coding interview. Reply with exactly one word: "
                     "approach (they describe a plan/algorithm/complexity), question (they ask the interviewer something), "
                     "or other.")

HINT_RE = re.compile(r"\b(hint|i'?m stuck|i am stuck|no idea|give me a clue|any tips?|can you help|nudge)\b", re.IGNORECASE)
APPROACH_RE = re.compile(r"\b(my approach|i('| wi)ll use|i would use|i'd use|brute force|O\([^)]*\)|time complexity|"
                         r"space complexity|amortized)\b", re.IGNORECASE)


def problem_prefix(p: Problem) -> str:
    """Static (cacheable) interviewer-only context: statement and rubric. Hints/follow-ups are delivered per turn."""
    rubric = getattr(p, "rubric", None) or (
        f"Patterns being assessed: {', '.join(p.patterns) or 'n/a'}. Target solve time: {p.target_minutes} min. "
        "Probe correctness on edge cases, state complexity unprompted, communicate while coding.")
    return f"PROBLEM: {p.title}\n\n{p.statement.strip()}\n\nINTERVIEWER-ONLY RUBRIC: {rubric}"


# ---------------------------------------------------------------- interviewer

@dataclass
class TurnResult:
    reply: str | None
    phase: str
    elapsed_min: float
    interjection: str | None = None
    hint_level: int | None = None
    hint_kind: str | None = None
    follow_up: str | None = None
    hints_used: int = 0


class Interviewer:
    def __init__(self, problem: Problem, fmt: SessionFormat, llm: LLMClient | None, store: InterviewStore,
                 session_id: int):
        self.problem, self.fmt, self.llm, self.store, self.sid = problem, fmt, llm, store, session_id
        self.transcript: list[tuple[str, str]] = []   # (role, text): role candidate|interviewer
        self.hints_used = 0
        self.follow_ups_injected = 0
        self.last_follow_up_min = 0.0
        self.said_approach = False
        self.first_approach_min: float | None = None
        self.first_code_min: float | None = None
        self.last_fired: dict[str, float] = {}
        self.interjections: list[str] = []
        self.timeline: list[tuple[float, str, int]] = []   # (elapsed, phase, code_chars)
        self.usage: dict[str, Usage] = {}
        self._last_code = ""

    # -- construction -------------------------------------------------------------------------
    @classmethod
    def start(cls, problem: Problem, format_name: str, llm: LLMClient | None, store: InterviewStore) -> tuple[Interviewer, str]:
        fmt = get_format(format_name)
        sid = store.create_session(problem.id, fmt.name)
        iv = cls(problem, fmt, llm, store, sid)
        if fmt.chat:
            opening = (f"Thanks for joining. Here's the problem: {problem.title}. {problem.statement.strip()} "
                       "Take a moment to ask any clarifying questions before you start.")
        else:
            opening = f"Online assessment: {problem.title}. {problem.statement.strip()} No interviewer interaction in this format."
        iv.transcript.append(("interviewer", opening))
        store.add_event(sid, "interviewer", "message", opening, 0.0, {"opening": True})
        return iv, opening

    @classmethod
    def restore(cls, problem: Problem, session: sqlite3.Row, llm: LLMClient | None, store: InterviewStore) -> Interviewer:
        """Rebuild in-memory state from persisted events (e.g. after a server restart)."""
        iv = cls(problem, get_format(session["format"]), llm, store, session["id"])
        for e in store.events(session["id"]):
            meta = json.loads(e["meta_json"]) if e["meta_json"] else {}
            t = e["elapsed_min"] or 0.0
            if e["kind"] == "message":
                if e["content"]:
                    iv.transcript.append((e["role"], e["content"]))
                if e["role"] == "candidate":
                    iv._last_code = meta.get("code", iv._last_code)
                    if meta.get("approach"):
                        iv.said_approach, iv.first_approach_min = True, iv.first_approach_min if iv.first_approach_min is not None else t
                    if meta.get("code_chars", 0) > 0 and iv.first_code_min is None:
                        iv.first_code_min = t
                    iv.timeline.append((t, meta.get("phase", ""), meta.get("code_chars", 0)))
            elif e["kind"] == "hint":
                iv.hints_used += 1
            elif e["kind"] == "follow_up":
                iv.follow_ups_injected += 1
                iv.last_follow_up_min = t
            elif e["kind"] == "interjection":
                iv.interjections.append(meta.get("rule", ""))
                iv.last_fired[meta.get("rule", "")] = t
            elif e["kind"] == "usage":
                iv.usage.setdefault(meta["model"], Usage()).add(Usage(**meta["usage"]))
        return iv

    # -- LLM plumbing -------------------------------------------------------------------------
    def _call(self, model: str, system: list[dict], messages: list[dict], max_tokens: int, elapsed: float) -> str:
        if self.llm is None:
            raise RuntimeError("no LLM client configured for this session format")
        r = self.llm.complete(model=model, system=system, messages=messages, max_tokens=max_tokens)
        self.usage.setdefault(model, Usage()).add(r.usage)
        cost = estimate_cost_usd(model, r.usage)
        log.info("llm call model=%s in=%d out=%d cache_w=%d cache_r=%d est_cost_usd=%.6f", model, r.usage.input_tokens,
                 r.usage.output_tokens, r.usage.cache_creation_input_tokens, r.usage.cache_read_input_tokens, cost)
        self.store.add_event(self.sid, "system", "usage", "", elapsed,
                             {"model": model, "usage": vars(r.usage), "est_cost_usd": cost})
        return r.text

    def _classify(self, text: str, elapsed: float) -> str:
        if HINT_RE.search(text):
            return "hint_request"
        if APPROACH_RE.search(text):
            return "approach"
        if self.said_approach or self.llm is None:
            return "other"
        try:
            out = self._call(CLASSIFIER_MODEL, [{"type": "text", "text": CLASSIFIER_SYSTEM}],
                             [{"role": "user", "content": text}], 5, elapsed).lower()
        except Exception as e:  # noqa: BLE001 - classification is best-effort
            log.warning("classifier failed: %s", e)
            return "other"
        for label in ("approach", "question"):
            if label in out:
                return label
        return "other"

    def _messages(self, state_and_directives: str) -> list[dict]:
        msgs: list[dict] = []
        for role, text in self.transcript:
            r = "user" if role == "candidate" else "assistant"
            if msgs and msgs[-1]["role"] == r:
                msgs[-1]["content"] += "\n" + text
            else:
                msgs.append({"role": r, "content": text})
        if not msgs or msgs[0]["role"] != "user":
            msgs.insert(0, {"role": "user", "content": "(session start)"})
        if msgs[-1]["role"] == "user":   # last user turn: append state + directives after the candidate's words
            msgs[-1]["content"] += "\n\n" + state_and_directives
        else:
            msgs.append({"role": "user", "content": state_and_directives})
        return msgs

    # -- the turn -----------------------------------------------------------------------------
    def turn(self, message: str, code: str, elapsed_min: float, silence_s: float = 0.0) -> TurnResult:
        message = (message or "").strip()
        phase = phase_at(self._pace_minute(elapsed_min))
        res = TurnResult(None, phase, elapsed_min, hints_used=self.hints_used)
        code_chars = len(code.strip())
        label = self._classify(message, elapsed_min) if message and self.fmt.chat else "other"
        if label == "approach" and not self.said_approach:
            self.said_approach, self.first_approach_min = True, elapsed_min
        if code_chars > 0 and self.first_code_min is None:
            self.first_code_min = elapsed_min
        self.timeline.append((elapsed_min, phase, code_chars))

        meta = {"phase": phase, "code_chars": code_chars, "silence_s": silence_s, "approach": label == "approach"}
        if code != self._last_code:
            meta["code"] = code   # snapshot only when it changed
            self._last_code = code
        if message or meta.get("code") is not None:
            self.store.add_event(self.sid, "candidate", "message", message, elapsed_min, meta)
            if message:
                self.transcript.append(("candidate", message))
        if not self.fmt.chat:
            return res   # OA: record only, no interviewer, no interruptions, no hints

        directives: list[str] = []
        rule_text = None
        hint = None
        if label == "hint_request":
            level = min(self.hints_used, len(HINT_LEVELS) - 1) + 1
            res.hint_level, res.hint_kind = level, HINT_LEVELS[level - 1]
            directives.append(f"HINT level {level} ({res.hint_kind}): {self._hint_material(level)}")
            hint = level
        due = self._follow_up_due(elapsed_min, code_chars)
        if due and hint is None:
            res.follow_up = self.problem.follow_ups[self.follow_ups_injected]
            directives.append("NEW REQUIREMENT: announce this as a new requirement or extension and ask how the "
                              f"design changes: {res.follow_up}")
        elif self.fmt.interrupts and hint is None:
            it = check(self._pace_minute(elapsed_min), silence_s, code_chars, self.said_approach)
            if it and elapsed_min - self.last_fired.get(it.kind, -1e9) >= INTERJECTION_COOLDOWN_MIN:
                res.interjection, rule_text = it.kind, it.message
                directives.append(f"INTERRUPT ({it.kind}): say this in your own words: {it.message}")
        if not message and not directives:
            return res

        system = [
            {"type": "text", "text": PERSONA},
            # Static problem/rubric prefix: cache breakpoint here so persona + problem are cached across turns.
            {"type": "text", "text": problem_prefix(self.problem), "cache_control": {"type": "ephemeral"}},
        ]
        state = (f"[state] elapsed {elapsed_min:.1f} of {self.fmt.total_min:.0f} min; phase: {phase}; "
                 f"silence {silence_s:.0f}s\n[code snapshot]\n{code if code.strip() else '(empty)'}")
        if directives:
            state += "\n[directives]\n" + "\n".join(directives)
        fallback = res.follow_up or rule_text
        try:
            reply = self._call(DIALOGUE_MODEL, system, self._messages(state), 1500, elapsed_min)
        except MissingAPIKeyError:
            raise
        except Exception as e:  # noqa: BLE001 - API trouble: fall back to the rule text so the session continues
            log.warning("dialogue call failed: %s", e)
            reply = fallback or ""
        if not reply or reply.strip() == "...":
            reply = fallback or ""
        res.reply = reply or None
        if res.reply:
            self.transcript.append(("interviewer", res.reply))
            self.store.add_event(self.sid, "interviewer", "message", res.reply, elapsed_min)
        # Record structured events after the reply so counts reflect only delivered coaching.
        if res.hint_level:
            self.hints_used += 1
            self.store.add_event(self.sid, "interviewer", "hint", res.reply or "", elapsed_min,
                                 {"level": res.hint_level, "kind": res.hint_kind})
        if res.follow_up:
            self.follow_ups_injected += 1
            self.last_follow_up_min = elapsed_min
            self.store.add_event(self.sid, "interviewer", "follow_up", res.follow_up, elapsed_min,
                                 {"index": self.follow_ups_injected})
        if res.interjection:
            self.interjections.append(res.interjection)
            self.last_fired[res.interjection] = elapsed_min
            self.store.add_event(self.sid, "interviewer", "interjection", res.reply or "", elapsed_min,
                                 {"rule": res.interjection})
        res.hints_used = self.hints_used
        return res

    # -- helpers ------------------------------------------------------------------------------
    def _pace_minute(self, elapsed: float) -> float:
        """pace.check is calibrated to a 45-minute slot; scale longer/shorter formats onto it."""
        return elapsed * 45.0 / self.fmt.total_min

    def _hint_material(self, level: int) -> str:
        hints = self.problem.hints
        if level == 1:
            return ("ask one guiding question that points toward the relevant idea "
                    f"(patterns: {', '.join(self.problem.patterns) or 'n/a'}) without naming the technique outright.")
        if level == 2:
            return (f"point at this idea without giving the full fix: {hints[0]}" if hints
                    else "point at the specific part of their approach or code that deserves attention.")
        return (f"give one concrete step based on this, leaving the rest to them: {hints[-1]}" if hints
                else "describe one concrete next step, leaving the rest to them.")

    def _follow_up_due(self, elapsed: float, code_chars: int) -> bool:
        w = self.fmt.follow_up_window
        if not w or self.follow_ups_injected >= len(self.problem.follow_ups):
            return False
        since = elapsed - self.last_follow_up_min
        # Inject after the minimum gap once there is code to extend; force it at the maximum gap.
        return since >= w[1] or (since >= w[0] and code_chars > 0)

    # -- finish -------------------------------------------------------------------------------
    def finish(self, passed: bool, elapsed_min: float) -> dict:
        pace_rows = []
        for name, s, e in PHASES_45:
            k = self.fmt.total_min / 45.0
            ts = [t for t in self.timeline if t[1] == name]
            pace_rows.append({"phase": name, "planned_start_min": round(s * k, 1), "planned_end_min": round(e * k, 1),
                              "turns": len(ts), "actual_first_turn_min": round(ts[0][0], 1) if ts else None,
                              "code_chars_at_end": ts[-1][2] if ts else None})
        total_usage, total_cost, by_model = Usage(), 0.0, {}
        for m, u in self.usage.items():
            c = estimate_cost_usd(m, u)
            total_usage.add(u)
            total_cost += c
            by_model[m] = {**vars(u), "est_cost_usd": round(c, 6)}
        target = self.problem.target_minutes
        summary = {
            "problem_id": self.problem.id, "format": self.fmt.name, "elapsed_min": round(elapsed_min, 1),
            "planned_total_min": self.fmt.total_min, "final_phase": phase_at(self._pace_minute(elapsed_min)),
            "pace": pace_rows,
            "first_approach_min": self.first_approach_min, "first_code_min": self.first_code_min,
            "planned_first_code_min": round(12 * self.fmt.total_min / 45.0, 1),
            "hints_used": self.hints_used,
            "interjections": {k: self.interjections.count(k) for k in sorted(set(self.interjections))},
            "follow_ups_injected": self.follow_ups_injected,
            "passed": passed,
            "ease": ease_for(passed, self.hints_used, elapsed_min, target),
            "usage": {"by_model": by_model, "total": vars(total_usage),
                      "est_cost_usd": round(total_cost, 6), "cost_is_estimate": True},
        }
        self.store.finish(self.sid, {"by_model": by_model, "total": vars(total_usage)}, total_cost, summary)
        return summary
