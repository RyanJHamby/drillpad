import ast
import builtins
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from drillpad.core.models import Problem, RunResult, TestCase, TestResult

# Self-run only: rlimits + timeout + scrubbed env. This does NOT block network access;
# a hosted/consumer version must run in a container or microVM instead.
MEM_BYTES = 512 * 1024 * 1024
CPU_SECONDS = 10

HARNESS = """
import json, sys, traceback
_results = []
def _run(name, hidden, fn, stage=0):
    try:
        fn()
        _results.append({"name": name, "passed": True, "hidden": hidden, "message": "", "stage": stage})
    except BaseException:
        msg = traceback.format_exc(limit=3).strip().splitlines()[-1]
        _results.append({"name": name, "passed": False, "hidden": hidden, "message": msg, "stage": stage})
"""


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    if sys.platform != "darwin":  # RLIMIT_AS is not enforced on macOS
        resource.setrlimit(resource.RLIMIT_AS, (MEM_BYTES, MEM_BYTES))


_IMPLICIT: dict[str, str] = {}


def _implicit_imports(problem: Problem) -> str:
    """Stdlib modules the TEST code uses without importing (e.g. `threading.Thread`): provide them so the
    candidate's solution does not need to import modules only the tests touch."""
    if problem.id in _IMPLICIT:
        return _IMPLICIT[problem.id]
    mods: set[str] = set()
    for t in problem.tests:
        try:
            tree = ast.parse(t.code)
        except SyntaxError:
            continue
        bound: set[str] = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                bound |= {a.asname or a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                bound |= {a.asname or a.name for a in n.names}
            elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                bound.add(n.name)
            elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                bound.add(n.id)
            elif isinstance(n, ast.arg):
                bound.add(n.arg)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                bound.add(n.name)
        for n in ast.walk(tree):  # only module-style use (`threading.Thread`), never bare names like `tokenize(...)`
            if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and isinstance(n.value.ctx, ast.Load)
                    and n.value.id in sys.stdlib_module_names and n.value.id not in bound
                    and not hasattr(builtins, n.value.id)):
                mods.add(n.value.id)
    _IMPLICIT[problem.id] = ("import " + ", ".join(sorted(mods))) if mods else ""
    return _IMPLICIT[problem.id]


def _gather_tests(problem: Problem) -> list[tuple[int, TestCase]]:
    """Gather tests with stage tags. If problem has stages, cumulative tests per stage; else flat tests."""
    if problem.stages:
        # Cumulative: stage k includes all tests 0..k
        result = []
        for stage_num, stage in enumerate(problem.stages):
            for test in stage.tests:
                result.append((stage_num, test))
        return result
    else:
        # No stages: all tests are stage 0
        return [(0, t) for t in problem.tests]


def _build_script(code: str, problem: Problem) -> str:
    # Graded runs must not execute the candidate's `if __name__ == "__main__":` driver block.
    parts = [HARNESS, _implicit_imports(problem), '__name__ = "solution"', problem.prelude, code, ""]
    tests = _gather_tests(problem)
    for i, (stage_num, t) in enumerate(tests):
        body = "\n".join("    " + line for line in t.code.strip().splitlines())
        parts.append(f"def _t{i}():\n{body}\n_run({t.name!r}, {t.hidden!r}, _t{i}, {stage_num})")
    parts.append("print('\\n__DRILLPAD__' + json.dumps(_results))")
    return "\n".join(parts)


def run(code: str, problem: Problem, timeout_s: float = 10.0) -> RunResult:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "main.py"
        script.write_text(_build_script(code, problem))
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(script)],
                cwd=tmp,
                env={"PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=timeout_s,
                preexec_fn=_limits,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            elapsed = int((time.monotonic() - start) * 1000)
            out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            return RunResult([], out, "timed out", True, elapsed)
        elapsed = int((time.monotonic() - start) * 1000)
    stdout, _, marker = proc.stdout.partition("\n__DRILLPAD__")
    results = [TestResult(**r) for r in json.loads(marker)] if marker else []
    return RunResult(results, stdout, proc.stderr, False, elapsed)


def run_scratch(code: str, stdin: str = "", timeout_s: float = 10.0, prelude: str = "") -> dict:
    """CoderPad-style run: execute the file as-is with optional stdin; no tests, no harness."""
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "main.py"
        script.write_text((prelude + "\n" if prelude else "") + code)
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(script)], cwd=tmp, env={"PATH": "/usr/bin:/bin"}, input=stdin,
                capture_output=True, text=True, timeout=timeout_s, preexec_fn=_limits, check=False,
            )
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            return {"stdout": out[-20000:], "stderr": "timed out", "timed_out": True, "exit_code": None,
                    "elapsed_ms": int((time.monotonic() - start) * 1000)}
        return {"stdout": proc.stdout[-20000:], "stderr": proc.stderr[-20000:], "timed_out": False,
                "exit_code": proc.returncode, "elapsed_ms": int((time.monotonic() - start) * 1000)}
