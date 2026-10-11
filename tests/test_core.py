import sqlite3

import pytest

from drillpad.content.loader import load_all
from drillpad.core import db
from drillpad.runner.python import run

SOLUTION = '''
class DynamicArray:
    def __init__(self):
        self._cap, self._n, self._d = 1, 0, [None]
    def __len__(self): return self._n
    def get(self, i):
        if not 0 <= i < self._n: raise IndexError(i)
        return self._d[i]
    def set(self, i, v):
        if not 0 <= i < self._n: raise IndexError(i)
        self._d[i] = v
    def append(self, v):
        if self._n == self._cap:
            self._cap *= 2
            self._d += [None] * (self._cap - self._n)
        self._d[self._n] = v; self._n += 1
    def pop(self):
        if self._n == 0: raise IndexError
        self._n -= 1; v = self._d[self._n]; self._d[self._n] = None; return v
'''


@pytest.fixture
def problem():
    return load_all()["dynamic-array"]


def test_correct_solution_passes(problem):
    assert run(SOLUTION, problem).passed


def test_starter_fails_without_crashing(problem):
    r = run(problem.starter, problem)
    assert not r.passed and r.results and not r.timed_out


def test_infinite_loop_times_out(problem):
    r = run("while True: pass", problem, timeout_s=1)
    assert r.timed_out and not r.passed


def test_syntax_error_reports_stderr(problem):
    r = run("def (", problem)
    assert not r.passed and r.stderr


def test_revisions_append_only(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    a = db.start_attempt(conn, "dynamic-array")
    assert db.add_revision(conn, a, "x", False, "[]", 5) == 1
    assert db.add_revision(conn, a, "y", True, "[]", 7) == 2
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE revisions SET code='z'")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM revisions")
    assert [r["code"] for r in db.revisions(conn, a)] == ["x", "y"]


def test_graded_run_skips_main_driver_and_stdin(problem):
    code = SOLUTION + '\nif __name__ == "__main__":\n    input()\n    raise SystemExit("driver ran")\n'
    r = run(code, problem, timeout_s=5)
    assert r.passed and not r.timed_out


def test_prelude_helpers_are_injected_so_editor_can_be_blank():
    """Tree/list problems keep TreeNode/build_tree out of the editor; the runner supplies them."""
    from drillpad.runner.python import run_scratch

    p = load_all()["max-depth-binary-tree"]
    assert "class TreeNode" in p.prelude and "TreeNode" not in p.starter
    code = "def max_depth(root):\n    return 0 if root is None else 1 + max(max_depth(root.left), max_depth(root.right))\n"
    r = run(code, p)
    assert r.passed, [x for x in r.results if not x.passed]
    s = run_scratch("print(build_tree([1, 2, 3]).left.val)", prelude=p.prelude)
    assert s["stdout"].strip() == "2"


def test_implicit_imports_only_for_module_style_use():
    from drillpad.core.models import Problem, TestCase
    from drillpad.runner.python import _implicit_imports, run

    t = TestCase("t", "h = []\nheapq.heappush(h, 3)\nassert f(h) == 3\ntokenize(h)\nimport json\njson.dumps(1)")
    p = Problem(id="synthetic", title="t", statement="", starter="", tests=[t])
    assert _implicit_imports(p) == "import heapq"  # not `tokenize` (a bare call) and not `json` (imported in-test)
    code = "def f(h):\n    return h[0]\ndef tokenize(h):\n    return h\n"
    assert run(code, p).passed  # candidate never imported heapq
    ps = load_all()
    assert all(_implicit_imports(q) == "" or "tokenize" not in _implicit_imports(q) for q in ps.values())
