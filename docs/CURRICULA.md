# Curricula

The course is organized as **curricula**: named learning tracks. The built-in `core` curriculum is the foundational course.
Focused curricula go deep on one subject (for example power grids and compute, or trading systems), can own their own modules,
and can reuse core modules instead of copying them. Curricula are pluggable: you can add one from the repository, from a
private folder, or from a separate git repository, without touching the rest.

```
core                      the staged foundational course (generated from content/paths.yaml)
power-grid-compute        owns grid, markets, datacenter modules; reuses gpu, cost, orchestration, data pipeline modules
trading-hft               owns microstructure, strategy, risk modules; reuses market data, latency, lock-free, C++ modules
your-own-track            from a folder you point drillpad at
```

## Where curricula load from

| Root | Path | Use it for |
|---|---|---|
| bundled | `src/drillpad/content/curricula/<id>/` | tracks that ship with the project |
| private | `<data dir>/private/curricula/<id>/` | tracks that stay on your machine (never exported) |
| external | any folder listed in `DRILLPAD_CURRICULA_PATH` (colon-separated) | a track kept in its own git repository |

An external root may be a folder of curricula or a single curriculum folder (the repository root can be the curriculum).
`drillpad curricula` lists what is loaded and from where.

## Anatomy of a curriculum

```
my-track/
  curriculum.yaml
  modules/<key>/module.yaml + lessons/*.md      modules this curriculum owns
```

```yaml
id: my-track                  # lowercase letters, digits, hyphens; 'core' is reserved
title: "My Track"
summary: What it teaches and for whom.
level: intermediate           # beginner | intermediate | advanced (informational)
status: draft                 # draft | active | complete
requires:
  curricula: [core]           # recommended earlier tracks (informational)
  modules: [reasoning-under-constraints]
levels:
  - id: foundations
    title: Foundations
    units:
      - module: first-topic            # owned: modules/first-topic/. Shown as "planned" until it exists.
        title: First Topic             # required while planned; summary is optional
        summary: What the module will cover.
      - uses: latency-systems          # reused: any existing module id; progress is shared with the core course
capstones:
  - id: build-something
    title: Build something
    brief: What to build and what to report.
```

- Owned modules get the global id `<curriculum-id>.<key>`, so independently written curricula cannot collide. Lesson progress and
  whiteboard history are keyed by that id.
- A **planned** unit is a roadmap entry: it appears greyed in the Learn page and becomes ready as soon as its module folder
  exists. Use planned units to lay out a whole track and fill it in over time.
- A **reused** unit points at an existing module. It appears in both tracks and counts toward both tracks' progress.
- A broken curriculum is skipped with a warning; it never stops the app.

## Working with curricula

```bash
python scripts/course.py new-curriculum my-track "My Track"                  # bundled with the repo
python scripts/course.py new-curriculum my-track "My Track" --private        # local only
python scripts/course.py new-curriculum my-track "My Track" --dest ~/dev/my-track   # standalone pack (its own git repo)
export DRILLPAD_CURRICULA_PATH=~/dev/my-track                                 # plug a standalone pack in

python scripts/course.py new-module first-topic --curriculum my-track "First Topic"   # write a module (or start a planned one)
python scripts/course.py new-lesson my-track.first-topic intro "Introduction"
python scripts/course.py check && python scripts/course.py docs
```

Lessons follow the same standard and review rules as the core course (see `MAINTAINING_THE_COURSE.md`).
