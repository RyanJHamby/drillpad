import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "publish_check.py"
spec = importlib.util.spec_from_file_location("publish_check", SCRIPT)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

REAL = pc.load_manifest()
needs_private_repo = pytest.mark.skipif(not (pc.ROOT / "docs/inputs").exists(), reason="private working repo only")
MANIFEST = {
    "include": ["src/**", "README.md", "LICENSE"],
    "exclude": ["src/private/**", "src/firms/*.yaml"],
    "keep": ["src/firms/generic-*.yaml"],
    "banned_patterns": REAL["banned_patterns"],
    "forbidden_files": REAL["forbidden_files"],
    "required": [{"file": "LICENSE", "reason": "needs a license"},
                 {"file": "README.md", "contains": "Scope and sources", "reason": "scope statement"}],
}


def tree(root: Path, files: dict[str, str]) -> list[str]:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    return list(files)


def test_select_is_default_deny_with_exclude_and_keep():
    files = ["src/a.py", "src/private/x.md", "src/firms/acme.yaml", "src/firms/generic-quant.yaml",
             "docs/inputs/companies.csv", "random.txt", "README.md"]
    shipped, withheld = pc.select(files, MANIFEST)
    assert shipped == ["src/a.py", "src/firms/generic-quant.yaml", "README.md"]
    assert set(withheld) == {"src/private/x.md", "src/firms/acme.yaml", "docs/inputs/companies.csv", "random.txt"}


def test_scan_flags_each_risk_class(tmp_path):
    # Samples are assembled from pieces so this file never contains the risky literals itself.
    samples = ["path /Us" + "ers/someone/notes", "see Desk" + "top/interview-prep/x.md", "mail a.b@" + "gmail.com",
               "key s" + "k-abcdefghijklmnopqrstuvwxyz0123", "claims it actu" + "ally tests this"]
    files = tree(tmp_path, {"README.md": "Scope and sources\n", "LICENSE": "MIT", "src/a.md": "\n".join(samples) + "\n",
                            "src/data.db": "binary",
                            "src/drillpad/content/packs/p.yaml": "statement: Exam" + "ple 1: nums = [2,7]\n"})
    found = "\n".join(pc.scan(tmp_path, files, MANIFEST))
    for rule in ("home-path", "local-docs-path", "email", "secret", "overclaim", "leetcode-boilerplate", "forbidden-file"):
        assert f"[{rule}]" in found, rule


def test_allowlisted_and_suppressed_matches_do_not_fire(tmp_path):
    files = tree(tmp_path, {
        "README.md": "Scope and sources\n", "LICENSE": "x",
        "src/a.md": ("contact noreply@anthropic.com or user@example.com\n"
                     "<!-- publish-ok: sourced from https://example.org/public-post -->\nShe said it actu" + "ally tests X\n"
                     "task-specs-agents-can-finish is not a key\n"),
    })
    assert pc.scan(tmp_path, files, MANIFEST) == []


def test_bare_suppression_without_reason_does_not_count(tmp_path):
    files = tree(tmp_path, {"README.md": "Scope and sources\n", "LICENSE": "x", "src/a.md": "publish-ok:\nit actu" + "ally tests X\n"})
    assert any("overclaim" in f for f in pc.scan(tmp_path, files, MANIFEST))


def test_required_files_and_readme_statement(tmp_path):
    files = tree(tmp_path, {"README.md": "no statement here", "src/a.md": "clean"})
    found = pc.scan(tmp_path, files, MANIFEST)
    assert any("LICENSE" in f and "required" in f for f in found)
    assert any("README.md" in f and "Scope and sources" in f for f in found)


def test_private_patterns_are_applied(tmp_path):
    files = tree(tmp_path, {"README.md": "Scope and sources\n", "LICENSE": "x", "src/a.md": "talked to Jane Recruiter\n"})
    extra = [{"id": "private-pattern", "pattern": "Jane Recruiter", "reason": "private"}]
    assert pc.scan(tmp_path, files, MANIFEST) == []
    assert any("private-pattern" in f for f in pc.scan(tmp_path, files, MANIFEST, extra))


def test_export_refuses_non_empty_or_in_repo_destination(tmp_path):
    full = tmp_path / "full"
    full.mkdir()
    (full / "x").write_text("x")

    class A:
        dest = str(full)

    with pytest.raises(SystemExit, match="not empty"):
        pc.cmd_export(A)

    class B:
        dest = str(pc.ROOT / "export-inside")

    with pytest.raises(SystemExit, match="outside this repository"):
        pc.cmd_export(B)


@needs_private_repo
def test_real_manifest_withholds_personal_material():
    files = pc.tracked_files()
    shipped, withheld = pc.select(files, REAL)
    withheld_set = set(withheld)
    for private in ("docs/inputs/companies.csv", "docs/inputs/problem_bank.csv", "docs/journal.md",
                    "src/drillpad/content/firms/INDEX.md", "src/drillpad/RESUME_CLAIM_WALKTHROUGHS.md"):
        assert private in withheld_set, private
    firm_files = [f for f in files if f.startswith("src/drillpad/content/firms/") and f.endswith(".yaml")]
    assert [f for f in firm_files if "/generic-" not in f and f in shipped] == [], "only generic firm profiles may ship"
    assert any("/generic-" in f for f in shipped)
    assert not any(f.endswith((".db", ".apkg")) for f in shipped)
    for pattern in REAL["exclude"]:
        if pattern.startswith(pc.MODULES_PREFIX):
            assert not [f for f in shipped if pc.matches(f, [pattern])], pattern


def test_strip_modules_from_paths_yaml_removes_stage_entries_and_requires(tmp_path):
    f = tmp_path / "paths.yaml"
    f.write_text("stages:\n  - id: s1\n    modules:\n      - keep-a\n      - secret-mod\n      - keep-b\n"
                 "requires:\n  keep-b:\n    - keep-a\n  secret-mod:\n    - keep-a\n    - keep-b\npaths: {}\n")
    pc.strip_modules_from_paths(f, {"secret-mod"})
    text = f.read_text()
    assert "secret-mod" not in text
    loaded = pc.yaml.safe_load(text)
    assert loaded["stages"][0]["modules"] == ["keep-a", "keep-b"] and loaded["requires"] == {"keep-b": ["keep-a"]}


def test_withheld_modules_are_those_with_no_shipped_file():
    files = ["src/drillpad/content/modules/a/module.yaml", "src/drillpad/content/modules/b/module.yaml",
             "src/drillpad/content/modules/b/lessons/x.md"]
    pairs = [(files[0], files[0])]
    assert pc.withheld_modules(files, pairs) == {"b"}


@needs_private_repo
def test_real_export_strips_whatever_it_withholds_from_paths_yaml(tmp_path):
    files = pc.tracked_files()
    pairs, _ = pc.plan(files, REAL)
    gone = pc.withheld_modules(files, pairs)
    pc.materialize(tmp_path, pairs, files)
    shipped_paths = (tmp_path / pc.PATHS_YAML).read_text()
    assert not any(m in shipped_paths for m in gone)
    assert all(v for v in (pc.yaml.safe_load(shipped_paths).get("requires") or {}).values())


@needs_private_repo
def test_real_plan_ships_public_readme_not_private_files():
    pairs, withheld = pc.plan(pc.tracked_files(), REAL)
    dests = {d for _, d in pairs}
    assert {d: s for s, d in pairs}["README.md"] == "publish/README.public.md"
    assert "AGENTS.md" in withheld and "CLAUDE.md" in withheld and "AGENTS.md" not in dests


def test_mirror_updates_adds_and_removes_only_tracked_files(tmp_path):
    stage, dest = tmp_path / "stage", tmp_path / "dest"
    for rel, text in {"a.txt": "new a", "b.txt": "same", "sub/c.txt": "added"}.items():
        (stage / rel).parent.mkdir(parents=True, exist_ok=True)
        (stage / rel).write_text(text)
    for rel, text in {"a.txt": "old a", "b.txt": "same", "gone.txt": "tracked, no longer exported", "scratch.txt": "untracked"}.items():
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        (dest / rel).write_text(text)
    new = ["a.txt", "b.txt", "sub/c.txt"]
    added, changed, removed = pc.mirror(stage, dest, ["a.txt", "b.txt", "gone.txt"], new, dry_run=True)
    assert (added, changed, removed) == (["sub/c.txt"], ["a.txt"], ["gone.txt"])
    assert (dest / "a.txt").read_text() == "old a" and (dest / "gone.txt").exists(), "dry run must not write"
    pc.mirror(stage, dest, ["a.txt", "b.txt", "gone.txt"], new)
    assert (dest / "a.txt").read_text() == "new a" and (dest / "sub/c.txt").read_text() == "added"
    assert not (dest / "gone.txt").exists() and (dest / "scratch.txt").exists(), "untracked files are never deleted"


def test_sync_refuses_a_destination_that_is_not_a_git_clone(tmp_path):
    class A:
        dest = str(tmp_path)
        dry_run = False

    with pytest.raises(SystemExit, match="not a git clone"):
        pc.cmd_sync(A)
