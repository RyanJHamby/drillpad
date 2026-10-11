"""C++ runner. Tests are statement blocks placed in generated functions; each test runs in its own forked
process (5s alarm) so crashes, UB aborts (UBSan) and hangs become test failures, not run failures."""

import tempfile
import time
from pathlib import Path

from drillpad.core.models import Problem, RunResult, TestCase, TestResult
from drillpad.runner._proc import run_cmd, scrubbed_env, toolchain_env


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

HEADERS = """
#include <algorithm>
#include <array>
#include <atomic>
#include <cassert>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <functional>
#include <future>
#include <iostream>
#include <list>
#include <map>
#include <memory>
#include <mutex>
#include <numeric>
#include <optional>
#include <queue>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <tuple>
#include <type_traits>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <variant>
#include <vector>
"""

TEST_MACROS = r"""
#include <csignal>
#include <sys/wait.h>
#include <unistd.h>
struct DrillpadTestFailure { std::string msg; };
#define CHECK(cond) do { if (!(cond)) throw DrillpadTestFailure{std::string("CHECK failed: " #cond " (line ") + std::to_string(__LINE__) + ")"}; } while (0)
#define CHECK_EQ(a, b) do { if (!((a) == (b))) throw DrillpadTestFailure{std::string("CHECK_EQ failed: " #a " == " #b " (line ") + std::to_string(__LINE__) + ")"}; } while (0)
#define CHECK_THROWS(expr) do { bool drillpad_threw = false; try { (void)(expr); } catch (...) { drillpad_threw = true; } if (!drillpad_threw) throw DrillpadTestFailure{std::string("expected exception: " #expr " (line ") + std::to_string(__LINE__) + ")"}; } while (0)
"""

MAIN = r"""
int main() {
    setvbuf(stdout, nullptr, _IONBF, 0);
    for (int i = 0; i < DRILLPAD_N; i++) {
        int fds[2];
        if (pipe(fds) != 0) return 2;
        pid_t pid = fork();
        if (pid == 0) {
            close(fds[0]);
            alarm(5);
            std::string res = "P";
            try { drillpad_tests[i](); }
            catch (const DrillpadTestFailure& f) { res = "F\t" + f.msg; }
            catch (const std::exception& e) { res = std::string("F\texception: ") + e.what(); }
            catch (...) { res = "F\tunknown exception"; }
            ssize_t w = write(fds[1], res.data(), res.size()); (void)w;
            _exit(0);
        }
        close(fds[1]);
        std::string res; char buf[512]; ssize_t n;
        while ((n = read(fds[0], buf, sizeof buf)) > 0) res.append(buf, n);
        close(fds[0]);
        int status = 0; waitpid(pid, &status, 0);
        std::string out;
        if (WIFSIGNALED(status)) {
            int sg = WTERMSIG(status);
            out = std::string("FAIL\t") + (sg == SIGALRM ? "timed out (>5s)" : "crashed: " + std::string(strsignal(sg)));
        } else if (res.empty()) out = "FAIL\tno result (undefined behaviour abort or exit)";
        else if (res[0] == 'P') out = "PASS\t";
        else out = "FAIL\t" + res.substr(2);
        printf("@@DRILLPAD\t%d\t%s\n", i, out.c_str());
    }
    return 0;
}
"""


def build_source(code: str, problem: Problem) -> str:
    tests = _gather_tests(problem)
    fns = []
    for i, (stage_num, t) in enumerate(tests):
        fns.append(f"static void drillpad_test_{i}() {{\n{t.code}\n}}")
    table = ", ".join(f"drillpad_test_{i}" for i in range(len(tests)))
    return "\n".join([HEADERS, TEST_MACROS, problem.prelude, code, "\n".join(fns),
                      f"#define DRILLPAD_N {len(tests)}",
                      f"static void (*drillpad_tests[])() = {{{table}}};", MAIN])


def _flags() -> list[str]:
    # AddressSanitizer hangs at startup on this macOS setup, so use UBSan plus libc++ hardening (bounds-checked
    # operator[], etc.) which abort -> the per-test process reports "crashed" instead of silent UB.
    return ["-std=c++20", "-O1", "-g0", "-pthread", "-fsanitize=undefined", "-fno-sanitize-recover=undefined",
            "-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE"]


def run(code: str, problem: Problem, timeout_s: float = 60.0) -> RunResult:
    with tempfile.TemporaryDirectory() as tmp:
        src, exe = Path(tmp) / "main.cpp", Path(tmp) / "prog"
        src.write_text(build_source(code, problem))
        start = time.monotonic()
        rc, _out, err, timed = run_cmd(["clang++", *_flags(), str(src), "-o", str(exe)], tmp, 60, toolchain_env())
        if timed or rc != 0:
            return RunResult([], "", err if not timed else "compile timed out", timed, int((time.monotonic() - start) * 1000), True)
        rc, out, err, timed = run_cmd([str(exe)], tmp, timeout_s, scrubbed_env())
    stdout, results = [], {}
    for line in out.splitlines():
        if line.startswith("@@DRILLPAD\t"):
            _, idx, status, *msg = line.split("\t", 3)
            results[int(idx)] = (status == "PASS", msg[0] if msg else "")
        else:
            stdout.append(line)
    tests = _gather_tests(problem)
    tr = [TestResult(t.name, results.get(i, (False, "no result"))[0], t.hidden, results.get(i, (False, "no result"))[1], stage_num)
          for i, (stage_num, t) in enumerate(tests)]
    return RunResult(tr, "\n".join(stdout), err, timed, int((time.monotonic() - start) * 1000))


def run_scratch(code: str, stdin: str = "", timeout_s: float = 10.0, prelude: str = "") -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        src, exe = Path(tmp) / "main.cpp", Path(tmp) / "prog"
        src.write_text(f"{HEADERS}\n{prelude}\n{code}")
        start = time.monotonic()
        rc, _o, err, timed = run_cmd(["clang++", *_flags(), str(src), "-o", str(exe)], tmp, 60, toolchain_env())
        if timed or rc != 0:
            return {"stdout": "", "stderr": err, "timed_out": timed, "exit_code": rc if rc is not None else -1,
                    "elapsed_ms": int((time.monotonic() - start) * 1000)}
        rc, out, err, timed = run_cmd([str(exe)], tmp, timeout_s, scrubbed_env(), stdin)
    return {"stdout": out[-20000:], "stderr": err[-20000:], "timed_out": timed, "exit_code": rc,
            "elapsed_ms": int((time.monotonic() - start) * 1000)}
