#!/usr/bin/env python3
"""Check and export a public copy of the repository without leaking private material.

  python scripts/publish_check.py check                 what would ship, and every finding (exit 1 if any)
  python scripts/publish_check.py export --dest DIR     copy only manifest-approved files into an empty DIR, then re-scan it
  python scripts/publish_check.py sync --dest CLONE     update an existing clone of the public repo to match (scans first; never commits or pushes)

Rules live in publish/manifest.yaml (default deny). Private regexes (names, employers) go in
<data dir>/private/publish-banned.txt, one per line, so they never appear in this public repo.
Nothing here pushes, creates a remote, or rewrites history.
"""

import argparse
import filecmp
import fnmatch
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "publish" / "manifest.yaml"
MAX_SCAN_BYTES = 2_000_000
SUPPRESS = re.compile(r"publish-ok:\s*\S")


def private_file(name: str) -> list[str]:
    sys.path.insert(0, str(ROOT / "src"))
    from drillpad.core import paths

    f = paths.private_dir() / name
    if not f.exists():
        return []
    return [ln.strip() for ln in f.read_text().splitlines() if ln.strip() and not ln.startswith("#")]


def load_manifest(path: Path = MANIFEST) -> dict:
    """The public manifest plus any private exclude patterns (kept outside the repo so they never ship)."""
    m = yaml.safe_load(path.read_text())
    m["exclude"] = list(m.get("exclude", [])) + private_file("publish-exclude.txt")
    return m


def private_patterns() -> list[dict]:
    return [{"id": "private-pattern", "pattern": ln, "reason": "matches a pattern in your private banned list"}
            for ln in private_file("publish-banned.txt")]


def tracked_files(root: Path = ROOT) -> list[str]:
    out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, check=True).stdout
    return [ln for ln in out.splitlines() if ln]


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, p) for p in patterns)


def select(files: list[str], manifest: dict) -> tuple[list[str], list[str]]:
    """Split repo-relative paths into (shipped, withheld) under the default-deny manifest."""
    shipped, withheld = [], []
    for f in files:
        ok = matches(f, manifest["include"]) and (not matches(f, manifest.get("exclude", [])) or matches(f, manifest.get("keep", [])))
        (shipped if ok else withheld).append(f)
    return shipped, withheld


def plan(files: list[str], manifest: dict) -> tuple[list[tuple[str, str]], list[str]]:
    """(source, destination) pairs that would ship, plus withheld paths. `rename` maps a source to a different destination."""
    shipped, withheld = select(files, manifest)
    pairs = [(f, f) for f in shipped]
    present = set(files)
    for src, dst in (manifest.get("rename") or {}).items():
        if src in present:
            pairs = [(s_, d_) for s_, d_ in pairs if d_ != dst]  # a renamed file replaces the same-named original
            pairs.append((src, dst))
    return sorted(pairs, key=lambda p: p[1]), withheld


MODULES_PREFIX = "src/drillpad/content/modules/"
PATHS_YAML = "src/drillpad/content/paths.yaml"


def withheld_modules(files: list[str], pairs: list[tuple[str, str]]) -> set[str]:
    """Module ids that exist in the repo but ship no file at all."""
    def ids(paths: list[str]) -> set[str]:
        return {p[len(MODULES_PREFIX):].split("/")[0] for p in paths if p.startswith(MODULES_PREFIX)}
    return ids(files) - ids([d for _, d in pairs])


def strip_modules_from_paths(path: Path, ids: set[str]) -> None:
    """Remove withheld module ids (and their `requires` entries) from a copied paths.yaml, so a public copy never names them."""
    if not ids or not path.exists():
        return
    alt = "|".join(re.escape(i) for i in sorted(ids))
    out, skipping = [], False
    for ln in path.read_text().split("\n"):
        if skipping and ln.startswith("    - "):
            continue
        skipping = False
        if re.fullmatch(rf"\s*- ({alt})", ln):
            continue
        m = re.fullmatch(r"  ([\w-]+):", ln)
        if m and m.group(1) in ids:
            skipping = True
            continue
        out.append(ln)
    path.write_text("\n".join(out))
    loaded = yaml.safe_load(path.read_text())
    assert all(v for v in (loaded.get("requires") or {}).values()), "stripping left an empty requires entry"


def materialize(dest: Path, pairs: list[tuple[str, str]], files: list[str] | None = None) -> None:
    for src, dst in pairs:
        out = dest / dst
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / src, out)
    if files is not None:
        strip_modules_from_paths(dest / PATHS_YAML, withheld_modules(files, pairs))


def scan(root: Path, files: list[str], manifest: dict, extra_patterns: list[dict] | None = None) -> list[str]:
    """Findings (as 'path:line: [rule] reason') for the given files under `root`."""
    findings = []
    rules = [(r, re.compile(r["pattern"]), [re.compile(a) for a in r.get("allow", [])])
             for r in manifest.get("banned_patterns", []) + (extra_patterns or [])]
    for f in files:
        name = f.rsplit("/", 1)[-1]
        if matches(f, manifest.get("forbidden_files", [])) or matches(name, manifest.get("forbidden_files", [])):
            findings.append(f"{f}: [forbidden-file] databases, backups, credentials, and Anki packages never ship")
            continue
        p = root / f
        if matches(f, manifest.get("scan_exempt", [])) or not p.is_file() or p.stat().st_size > MAX_SCAN_BYTES:
            continue
        lines = p.read_text(errors="ignore").splitlines()
        for i, line in enumerate(lines, 1):
            suppressed = SUPPRESS.search(line) or (i > 1 and SUPPRESS.search(lines[i - 2]))
            for rule, rx, allow in rules:
                if rule.get("paths") and not matches(f, rule["paths"]):
                    continue
                for m in rx.finditer(line):
                    if suppressed or any(a.fullmatch(m.group(0)) for a in allow):
                        continue
                    findings.append(f"{f}:{i}: [{rule['id']}] {rule['reason']}")
    for req in manifest.get("required", []):
        target = root / req["file"]
        if not target.exists():
            findings.append(f"{req['file']}: [required] missing: {req['reason']}")
        elif req.get("contains") and req["contains"] not in target.read_text(errors="ignore"):
            findings.append(f"{req['file']}: [required] must contain '{req['contains']}': {req['reason']}")
    return findings


def cmd_check(_a) -> int:
    manifest = load_manifest()
    files = tracked_files()
    pairs, withheld = plan(files, manifest)
    with tempfile.TemporaryDirectory() as tmp:
        materialize(Path(tmp), pairs, files)
        findings = scan(Path(tmp), [d for _, d in pairs], manifest, private_patterns())
    print(f"{len(pairs)} tracked files would ship; {len(withheld)} are withheld by the manifest.")
    for f in findings:
        print(" ", f)
    print("clean" if not findings else f"{len(findings)} finding(s): resolve, suppress with a sourced `publish-ok:`, or exclude")
    return 1 if findings else 0


def cmd_export(a) -> int:
    dest = Path(a.dest).expanduser().resolve()
    if dest == ROOT or ROOT in dest.parents:
        raise SystemExit("choose a destination outside this repository")
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"{dest} is not empty; refusing to write into it")
    manifest = load_manifest()
    files = tracked_files()
    pairs, _ = plan(files, manifest)
    materialize(dest, pairs, files)
    findings = scan(dest, [d for _, d in pairs], manifest, private_patterns())
    print(f"exported {len(pairs)} files to {dest}")
    for f in findings:
        print(" ", f)
    if findings:
        print(f"{len(findings)} finding(s) in the export: do not publish it until they are resolved (nothing was pushed)")
        return 1
    print("export is clean; initialize a fresh repository there (new history) when ready. Nothing was pushed.")
    return 0


def mirror(stage: Path, dest: Path, dest_tracked: list[str], new_files: list[str], dry_run: bool = False) -> tuple[list[str], list[str], list[str]]:
    """Make `dest` match `stage` for the files the export owns. Returns (added, changed, removed).
    Only files git already tracks in `dest` can be removed; untracked files and .git are never touched."""
    added, changed = [], []
    for rel in new_files:
        src, tgt = stage / rel, dest / rel
        if not tgt.exists():
            added.append(rel)
        elif not filecmp.cmp(src, tgt, shallow=False):
            changed.append(rel)
        else:
            continue
        if not dry_run:
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, tgt)
    removed = sorted(set(dest_tracked) - set(new_files))
    if not dry_run:
        for rel in removed:
            (dest / rel).unlink(missing_ok=True)
    return added, changed, removed


def cmd_sync(a) -> int:
    dest = Path(a.dest).expanduser().resolve()
    if dest == ROOT or ROOT in dest.parents:
        raise SystemExit("choose the public clone, which must be outside this repository")
    if not (dest / ".git").exists():
        raise SystemExit(f"{dest} is not a git clone; create the public repository first (see docs/MAINTAINING_THE_COURSE.md)")
    manifest = load_manifest()
    files = tracked_files()
    pairs, _ = plan(files, manifest)
    new_files = [d for _, d in pairs]
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "export"
        materialize(stage, pairs, files)
        findings = scan(stage, new_files, manifest, private_patterns())
        if findings:
            for f in findings:
                print(" ", f)
            print(f"{len(findings)} finding(s): refusing to touch {dest}")
            return 1
        dest_tracked = subprocess.run(["git", "-C", str(dest), "ls-files"], capture_output=True, text=True, check=True).stdout.split()
        added, changed, removed = mirror(stage, dest, dest_tracked, new_files, a.dry_run)
    print(f"{'would sync' if a.dry_run else 'synced'} {dest}: {len(added)} added, {len(changed)} changed, {len(removed)} removed")
    for label, items in (("added", added), ("changed", changed), ("removed", removed)):
        for rel in items[:15]:
            print(f"  {label}: {rel}")
        if len(items) > 15:
            print(f"  ... and {len(items) - 15} more {label}")
    print("Review with `git -C <dest> diff`, then commit (signed) and push from the public clone. Nothing was committed or pushed.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    e = sub.add_parser("export")
    e.add_argument("--dest", required=True)
    e.set_defaults(fn=cmd_export)
    sy = sub.add_parser("sync")
    sy.add_argument("--dest", required=True)
    sy.add_argument("--dry-run", action="store_true")
    sy.set_defaults(fn=cmd_sync)
    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
