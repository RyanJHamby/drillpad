"""Language dispatch: graded runs and scratch runs for python / cpp / rust problems."""

from drillpad.core.models import Problem, RunResult
from drillpad.runner import cpp, python, rust

EXT = {"python": ".py", "cpp": ".cpp", "rust": ".rs"}
MONACO = {"python": "python", "cpp": "cpp", "rust": "rust"}


def run_problem(code: str, problem: Problem) -> RunResult:
    if problem.language == "cpp":
        return cpp.run(code, problem)
    if problem.language == "rust":
        return rust.run(code, problem)
    return python.run(code, problem)


def run_scratch(code: str, stdin: str = "", problem: Problem | None = None) -> dict:
    lang = problem.language if problem else "python"
    prelude = problem.prelude if problem else ""
    if lang == "cpp":
        return cpp.run_scratch(code, stdin, prelude=prelude)
    if lang == "rust":
        return rust.run_scratch(code, stdin, prelude=prelude)
    return python.run_scratch(code, stdin, prelude=prelude)
