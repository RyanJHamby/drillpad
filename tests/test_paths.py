"""Tests for paths.yaml learning path configuration."""

from pathlib import Path

import yaml


def test_paths_yaml_parses():
    """paths.yaml must be valid YAML."""
    paths_file = Path(__file__).parent.parent / "src/drillpad/content/paths.yaml"
    assert paths_file.exists(), "paths.yaml not found"
    paths = yaml.safe_load(paths_file.read_text())
    assert paths, "paths.yaml is empty or malformed"
    assert "stages" in paths, "Missing 'stages' in paths.yaml"
    assert "paths" in paths, "Missing 'paths' in paths.yaml"

def test_all_modules_placed():
    """Every on-disk module appears in exactly one stage."""
    paths_file = Path(__file__).parent.parent / "src/drillpad/content/paths.yaml"
    modules_dir = Path(__file__).parent.parent / "src/drillpad/content/modules"

    paths = yaml.safe_load(paths_file.read_text())
    on_disk = {d.name for d in modules_dir.iterdir() if d.is_dir()}

    # Collect modules in paths
    placed = set()
    for stage in paths.get("stages", []):
        for mod in stage.get("modules", []):
            assert mod not in placed, f"Module {mod} appears in multiple stages"
            placed.add(mod)

    # Always modules
    for mod in paths.get("always", []):
        placed.add(mod)

    # Check: every on-disk module is placed
    unplaced = on_disk - placed
    assert not unplaced, f"Modules not in paths.yaml: {unplaced}. Add to 'Unsorted' or a stage."

def test_requires_acyclic():
    """Prerequisites must not have cycles."""
    paths_file = Path(__file__).parent.parent / "src/drillpad/content/paths.yaml"
    paths = yaml.safe_load(paths_file.read_text())
    requires = paths.get("requires", {})

    # Simple cycle detection: DFS
    def has_cycle(node, visited, rec_stack):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in requires.get(node, []):
            if neighbor not in visited:
                if has_cycle(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.remove(node)
        return False

    visited, rec_stack = set(), set()
    for node in requires:
        if node not in visited:
            assert not has_cycle(node, visited, rec_stack), f"Cycle detected involving {node}"

def test_requires_references_exist():
    """Prerequisites must reference modules that exist."""
    paths_file = Path(__file__).parent.parent / "src/drillpad/content/paths.yaml"
    modules_dir = Path(__file__).parent.parent / "src/drillpad/content/modules"

    paths = yaml.safe_load(paths_file.read_text())
    on_disk = {d.name for d in modules_dir.iterdir() if d.is_dir()}

    # Add placed modules to valid set
    valid = set(on_disk)
    for stage in paths.get("stages", []):
        for mod in stage.get("modules", []):
            valid.add(mod)
    for mod in paths.get("always", []):
        valid.add(mod)

    # Check requires
    requires = paths.get("requires", {})
    for mod, deps in requires.items():
        for dep in deps:
            assert dep in valid, f"Module {mod} requires unknown module {dep}"
