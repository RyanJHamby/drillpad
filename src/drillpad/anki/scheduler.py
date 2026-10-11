from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DueCard:
    card_id: int
    problem_id: str


class Scheduler(Protocol):
    def due(self, queries: dict[str, list[str]], include_new: bool = False) -> list[DueCard]:
        """queries maps problem_id -> Anki search expressions linking it to cards."""
        ...

    def answer(self, card_id: int, ease: int) -> None: ...


def ease_for(passed: bool, hints_used: int, elapsed_min: float, target_min: float) -> int:
    """Map an attempt to Anki ease: 1=Again 2=Hard 3=Good 4=Easy."""
    if not passed:
        return 1
    if hints_used > 0 or elapsed_min > target_min:
        return 2
    return 4 if elapsed_min <= target_min * 0.6 else 3
