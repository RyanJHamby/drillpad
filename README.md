# drillpad

A local-first environment for learning systems engineering and practicing interview-style coding problems.
Everything runs on your own machine and your data stays there.

- **Learn:** a course of lessons organized into stages, from hardware and concurrency through distributed systems,
  operating production systems, and AI infrastructure. Each lesson has diagrams, a worked failure scenario, interview
  questions with follow-ups, and a checklist.
- **Practice:** a local code editor and runner with problem packs (Python, C++, Rust), hidden tests, hints, and follow-up
  stages that extend a problem.
- **Whiteboard tracker:** log a 1-5 self-score after you redraw a lesson from memory. Lessons come back on a spaced schedule
  (FSRS), and a queue shows what is due.
- **Progress and planning:** readiness by level, weak-area tracking, and a study planner.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run drillpad serve            # http://127.0.0.1:8765  (localhost only)
```

Open `http://127.0.0.1:8765/learn`. On macOS you can run it as a login item so a bookmark always works:

```bash
uv run drillpad service install   # starts at login, restarts if it crashes
uv run drillpad service status
uv run drillpad service uninstall
```

## Your data stays local

`uv run drillpad paths` shows where things live (macOS: `~/Library/Application Support/drillpad/`): the database,
rotating consistent backups, and an optional private overlay for modules or profiles you do not want in the repository.
Set `DRILLPAD_BACKUP_DIR` for an extra copy of each backup (for example a folder in a cloud-synced drive). The server
binds to `127.0.0.1` only and runs the code you type, so do not expose it to a network.

## The course

`python scripts/course.py check` verifies the course (every module placed, lessons listed, generated docs fresh);
`report` lists thin lessons, open `[VERIFY]` tags, and stale or unverified lessons; `new-lesson` and `new-module` scaffold
additions. See [`docs/MAINTAINING_THE_COURSE.md`](docs/MAINTAINING_THE_COURSE.md).

## Scope and sources

This is an independent study project. It is not affiliated with, sponsored by, or endorsed by any company it mentions;
names appear only to identify what an example or term refers to. It is meant to contain no confidential or non-public
interview material, and contributions must not include any (see [`CONTRIBUTING.md`](CONTRIBUTING.md)). Practice problems
are reworded and reference public problem lists by title; scoring weights and point values are the author's own design
choices, not any firm's published rubric.

## How this was built

Design, experiments, and analysis are mine. I used AI coding assistants for parts of the implementation, tests, and
documentation, and reviewed every change, with one exception described next.

The course content under `src/drillpad/content/modules/` was not reviewed that way: most of those lessons were drafted
by AI models from my prompts and outlines, and have not yet had a systematic accuracy review. Treat them as study notes,
not sources. A lesson carries a `Last verified: YYYY-MM-DD` line only after it has been checked against primary sources,
and unverified claims are tagged `[VERIFY]`.

## History

This repository starts at its first public snapshot. Earlier development happened in a private working repository,
which also holds material that is deliberately not published (personal practice data and notes). Releases are copied here from
that repository after an automated scan.

## License

Code: MIT (`LICENSE`). Course content and documentation: CC BY 4.0 (`LICENSE-CONTENT.md`).
