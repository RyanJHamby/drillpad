from pathlib import Path

import yaml

from drillpad.core.models import Complexity, Extension, Problem, Stage, TestCase

PACKS_DIR = Path(__file__).parent / "packs"


def load_problem(path: Path) -> Problem:
    d = yaml.safe_load(path.read_text())

    # Load stages if present; otherwise load flat tests
    stages = []
    tests = []
    if "stages" in d:
        for stage_data in d.pop("stages"):
            stage_tests = [TestCase(**t) for t in stage_data.pop("tests", [])]
            stages.append(Stage(tests=stage_tests, **stage_data))
            # Accumulate all cumulative tests for backward compatibility with test validators
            tests.extend(stage_tests)
    else:
        # Load flat tests for problems without stages
        tests = [TestCase(**t) for t in d.pop("tests", [])]

    complexity = [Complexity(**c) for c in d.pop("complexity", [])]
    extensions = [Extension(**e) for e in d.pop("extensions", [])]
    return Problem(tests=tests, stages=stages, complexity=complexity, extensions=extensions, **d)


def load_all(packs_dir: Path = PACKS_DIR) -> dict[str, Problem]:
    problems = [load_problem(p) for p in sorted(packs_dir.rglob("*.yaml"))]
    by_id = {p.id: p for p in problems}
    if len(by_id) != len(problems):
        raise ValueError("duplicate problem ids in packs")
    return by_id
