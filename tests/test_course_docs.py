"""The course's counts, docs, and learning path must stay consistent with what is on disk."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "course.py"
spec = importlib.util.spec_from_file_location("course", SCRIPT)
course = importlib.util.module_from_spec(spec)
spec.loader.exec_module(course)


def test_course_integrity_and_docs_are_fresh():
    errors, _warns = course.problems(course.load_modules(), course.load_paths())
    assert not errors, "run `python scripts/course.py docs` or fix:\n" + "\n".join(errors)


def test_lesson_scaffold_is_additive_and_refuses_overwrite(tmp_path, monkeypatch):
    mod = tmp_path / "demo"
    (mod / "lessons").mkdir(parents=True)
    (mod / "module.yaml").write_text('id: demo\ntitle: "Demo"\nlanguage: systems\ndescription: "d"\nlessons:\n'
                                     '- id: 01-first\n  title: "First"\n  practice: []\n')
    (mod / "lessons" / "01-first.md").write_text("# First\n")
    monkeypatch.setattr(course, "MODULES", tmp_path)
    monkeypatch.setattr(course, "ROOT", tmp_path)
    before = (mod / "module.yaml").read_text()

    class A:
        module, slug, title = "demo", "second", 'Second "quoted"'

    assert course.cmd_new_lesson(A) == 0
    after = (mod / "module.yaml").read_text()
    assert after.startswith(before), "existing yaml must be untouched; new entries are appended"
    assert (mod / "lessons" / "02-second.md").exists()
    loaded = course.load_modules()["demo"]
    assert [ls["id"] for ls in loaded["lessons"]] == ["01-first", "02-second"]
    assert (mod / "lessons" / "01-first.md").read_text() == "# First\n"


def test_private_module_scaffold_stays_in_the_overlay_and_never_touches_the_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("DRILLPAD_PRIVATE_DIR", str(tmp_path / "priv"))
    paths_before = course.PATHS.read_text()

    class NewModule:
        id, stage, title, language, private = "my-private-notes", "My Private Notes", None, "systems", True

    assert course.cmd_new_module(NewModule) == 0
    d = tmp_path / "priv" / "modules" / "my-private-notes"
    assert (d / "module.yaml").exists() and course.PATHS.read_text() == paths_before, "paths.yaml must not change"
    assert "my-private-notes" not in course.load_modules(), "private modules are not part of the bundled course"

    class NewLesson:
        module, slug, title = "my-private-notes", "first", "First"

    assert course.cmd_new_lesson(NewLesson) == 0
    assert (d / "lessons" / "01-first.md").exists() and "01-first" in (d / "module.yaml").read_text()
    assert not (course.MODULES / "my-private-notes").exists()
