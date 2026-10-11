"""Rust runner. Tests are statement blocks in a generated `match`; the binary re-executes itself once per test
(10s limit) so panics, stack overflows and hangs become test failures."""

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

MAIN = r"""
fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() > 2 && args[1] == "--drillpad-test" {
        let i: usize = args[2].parse().unwrap();
        drillpad_test(i);
        return;
    }
    use std::io::Read;
    use std::process::{Command, Stdio};
    let exe = std::env::current_exe().unwrap();
    for i in 0..DRILLPAD_N {
        let mut child = Command::new(&exe).args(["--drillpad-test", &i.to_string()])
            .stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().unwrap();
        let mut so = child.stdout.take().unwrap();
        let mut se = child.stderr.take().unwrap();
        let th_o = std::thread::spawn(move || { let mut s = String::new(); let _ = so.read_to_string(&mut s); s });
        let th_e = std::thread::spawn(move || { let mut s = String::new(); let _ = se.read_to_string(&mut s); s });
        let start = std::time::Instant::now();
        let mut timed_out = false;
        let status = loop {
            if let Some(st) = child.try_wait().unwrap() { break Some(st); }
            if start.elapsed().as_secs() >= 10 { let _ = child.kill(); let _ = child.wait(); timed_out = true; break None; }
            std::thread::sleep(std::time::Duration::from_millis(5));
        };
        let out = th_o.join().unwrap();
        let err = th_e.join().unwrap();
        for l in out.lines() { println!("{}", l); }
        let (res, msg) = if timed_out { ("FAIL", "timed out (>10s)".to_string()) }
            else if status.unwrap().success() { ("PASS", String::new()) }
            else {
                let m: Vec<&str> = err.lines().filter(|l| !l.starts_with("note:") && !l.contains("RUST_BACKTRACE")).collect();
                let tail = if m.len() > 1 { m[1..].join(" ") } else { m.join(" ") };
                ("FAIL", if tail.is_empty() { "crashed".to_string() } else { tail })
            };
        println!("@@DRILLPAD\t{}\t{}\t{}", i, res, msg.replace('\n', " "));
    }
}
"""


def build_source(code: str, problem: Problem) -> str:
    tests = _gather_tests(problem)
    arms = "\n".join(f"        {i} => {{\n{t.code}\n        }}" for i, (stage_num, t) in enumerate(tests))
    return "\n".join(["#![allow(dead_code, unused, unused_must_use)]", problem.prelude, code,
                      f"const DRILLPAD_N: usize = {len(tests)};",
                      f"fn drillpad_test(i: usize) {{\n    match i {{\n{arms}\n        _ => {{}}\n    }}\n}}", MAIN])


FLAGS = ["--edition", "2021", "-C", "opt-level=1", "-C", "overflow-checks=on", "-C", "debuginfo=0"]


def run(code: str, problem: Problem, timeout_s: float = 90.0) -> RunResult:
    with tempfile.TemporaryDirectory() as tmp:
        src, exe = Path(tmp) / "main.rs", Path(tmp) / "prog"
        src.write_text(build_source(code, problem))
        start = time.monotonic()
        rc, _o, err, timed = run_cmd(["rustc", *FLAGS, str(src), "-o", str(exe)], tmp, 90, toolchain_env())
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
        src, exe = Path(tmp) / "main.rs", Path(tmp) / "prog"
        src.write_text(f"{prelude}\n{code}")
        start = time.monotonic()
        rc, _o, err, timed = run_cmd(["rustc", *FLAGS, str(src), "-o", str(exe)], tmp, 90, toolchain_env())
        if timed or rc != 0:
            return {"stdout": "", "stderr": err, "timed_out": timed, "exit_code": rc if rc is not None else -1,
                    "elapsed_ms": int((time.monotonic() - start) * 1000)}
        rc, out, err, timed = run_cmd([str(exe)], tmp, timeout_s, scrubbed_env(), stdin)
    return {"stdout": out[-20000:], "stderr": err[-20000:], "timed_out": timed, "exit_code": rc,
            "elapsed_ms": int((time.monotonic() - start) * 1000)}
