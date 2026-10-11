from dataclasses import dataclass, field


@dataclass(frozen=True)
class TestCase:
    name: str
    code: str
    hidden: bool = False
    tags: list[str] = field(default_factory=list)  # edge-case categories, see core/taxonomy.py


@dataclass(frozen=True)
class Complexity:
    op: str  # operation or "overall"
    time: str  # canonical, e.g. "O(1) amortized"
    space: str
    accepted_time: list[str] = field(default_factory=list)  # alternative accepted answers
    accepted_space: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Extension:
    q: str  # follow-up an interviewer would ask
    key_points: list[str]  # rubric points; credit is per point covered
    kind: str = "reasoning"  # reasoning | complexity | design | code


@dataclass(frozen=True)
class Stage:
    level: int  # 0 = base problem, 1..N follow-ups or parts
    kind: str  # "part" (multi-part problem) or "followup" (escalating follow-up)
    prompt: str  # stage-specific instructions (appended to base problem statement for level>0)
    tests: list[TestCase]  # cumulative: stage k includes all tests from stages 0..k
    minutes: int = 0  # target time for this stage (0 = inherit from problem)


@dataclass(frozen=True)
class Problem:
    id: str
    title: str
    statement: str
    starter: str
    tests: list[TestCase]
    patterns: list[str] = field(default_factory=list)
    firm_tags: list[str] = field(default_factory=list)
    bar_level: int = 1
    target_minutes: int = 20
    hints: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
    complexity: list[Complexity] = field(default_factory=list)
    extensions: list[Extension] = field(default_factory=list)
    narration: list[str] = field(default_factory=list)  # what to say aloud while solving (from source notes)
    state_aloud: list[str] = field(default_factory=list)  # edge cases to state unprompted
    categories: list[str] = field(default_factory=list)  # leetcode | systems-impl | trading | fintech | ai-infra
    language: str = "python"  # python | cpp | rust (python is the platform default)
    prelude: str = ""  # helper code (TreeNode, builders, constants) injected before the candidate's code
    walkthrough: str = ""  # short explanation of the reference solution
    anki_queries: list[str] = field(default_factory=list)  # Anki search syntax; notes are never modified
    stages: list[Stage] = field(default_factory=list)  # progressive stages (empty = no stages, single-shot problem)


@dataclass(frozen=True)
class TestResult:
    name: str
    passed: bool
    hidden: bool
    message: str = ""
    stage: int = 0  # which stage this test belongs to (0 = base problem, 1+ = follow-ups/parts)


@dataclass(frozen=True)
class RunResult:
    results: list[TestResult]
    stdout: str
    stderr: str
    timed_out: bool
    elapsed_ms: int
    compile_error: bool = False

    @property
    def passed(self) -> bool:
        return not self.timed_out and bool(self.results) and all(r.passed for r in self.results)

    def highest_passed_stage(self) -> int:
        """Return the highest stage where all tests passed (cumulative: stage k includes all tests 0..k)."""
        if self.timed_out or self.compile_error or not self.results:
            return -1
        stages = {r.stage for r in self.results}
        passed_stages = []
        for stage in sorted(stages):
            if all(r.passed for r in self.results if r.stage <= stage):
                passed_stages.append(stage)
        return max(passed_stages) if passed_stages else -1
