from dataclasses import dataclass

# (name, start_min, end_min) for a 45-minute live slot.
PHASES_45 = [("clarify", 0, 5), ("approach", 5, 12), ("code", 12, 30), ("test", 30, 38), ("followups", 38, 45)]


def phase_at(minute: float, phases=PHASES_45) -> str:
    for name, _, end in phases:
        if minute < end:
            return name
    return "over"


@dataclass(frozen=True)
class Interjection:
    kind: str
    message: str


def check(minute: float, silence_s: float, code_chars: int, said_approach: bool) -> Interjection | None:
    """Rule-based interrupts; first match wins. The LLM only phrases/extends these."""
    if minute >= 45:
        return Interjection("over", "We're out of time. Let's wrap up: complexity and what you'd do next.")
    if silence_s > 60:
        return Interjection("silence", "You've gone quiet. What are you thinking through?")
    if minute >= 12 and code_chars == 0:
        return Interjection("no_code", "We're at twelve minutes. Can you commit to an approach and start coding?")
    if minute >= 7 and not said_approach:
        return Interjection("no_approach", "What's your approach, and what's its complexity?")
    if minute >= 30 and phase_at(minute) == "test" and code_chars < 80:
        return Interjection("behind", "You're behind pace. Get a working version before optimizing.")
    return None
