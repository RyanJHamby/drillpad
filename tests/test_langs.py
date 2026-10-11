import pytest

from drillpad.core.models import Problem, TestCase
from drillpad.runner import registry
from drillpad.runner._proc import have

pytestmark = pytest.mark.skipif(not (have("clang++") and have("rustc")), reason="needs clang++ and rustc")


def cpp_problem():
    tests = [
        TestCase("adds", "CHECK_EQ(add(2, 3), 5);"),
        TestCase("fails", "CHECK_EQ(add(2, 2), 5);"),
        TestCase("crashes", "int* p = nullptr; volatile int x = *p; (void)x;"),
        TestCase("hangs", "while (true) {}"),
        TestCase("throws", "throw std::runtime_error(\"boom\");"),
    ]
    return Problem(id="cpp-synth", title="t", statement="", starter="", tests=tests, language="cpp")


def rust_problem():
    tests = [
        TestCase("adds", "assert_eq!(add(2, 3), 5);"),
        TestCase("fails", "assert_eq!(add(2, 2), 5, \"math is hard\");"),
        TestCase("panics", "let v: Vec<i32> = vec![]; let _ = v[3];"),
        TestCase("hangs", "loop {}"),
    ]
    return Problem(id="rs-synth", title="t", statement="", starter="", tests=tests, language="rust")


def test_cpp_each_test_isolated():
    r = registry.run_problem("int add(int a, int b) { return a + b; }", cpp_problem())
    assert not r.compile_error, r.stderr
    got = {x.name: x for x in r.results}
    assert got["adds"].passed and not got["fails"].passed
    assert not got["crashes"].passed and not got["hangs"].passed and "timed out" in got["hangs"].message
    assert not got["throws"].passed and "boom" in got["throws"].message


def test_cpp_compile_error_is_reported():
    r = registry.run_problem("int add(int a, int b) { return a +; }", cpp_problem())
    assert r.compile_error and not r.passed and "error" in r.stderr


def test_rust_each_test_isolated():
    r = registry.run_problem("fn add(a: i32, b: i32) -> i32 { a + b }", rust_problem())
    assert not r.compile_error, r.stderr
    got = {x.name: x for x in r.results}
    assert got["adds"].passed and not got["fails"].passed and "math is hard" in got["fails"].message
    assert not got["panics"].passed and not got["hangs"].passed and "timed out" in got["hangs"].message


def test_rust_compile_error_is_reported():
    r = registry.run_problem("fn add(a: i32, b: i32) -> i32 { a + }", rust_problem())
    assert r.compile_error and not r.passed


def test_scratch_runs_with_stdin():
    out = registry.run_scratch('#include <iostream>\nint main(){int x;std::cin>>x;std::cout<<x*2;}', "21",
                               cpp_problem())
    assert out["stdout"].strip() == "42" and out["exit_code"] == 0
    out = registry.run_scratch('fn main(){let mut s=String::new();std::io::stdin().read_line(&mut s).unwrap();'
                               'println!("{}", s.trim().len());}', "hello\n", rust_problem())
    assert out["stdout"].strip() == "5", out
