# Changelog

All notable changes are listed here. The project follows semantic versioning once it reaches 1.0; until then minor versions may change behavior.

## 0.1.0 (alpha)

First public snapshot.

- Lessons organized into curricula: a foundational `core` course plus `trading-hft` and `power-grid-compute` tracks (roadmaps that reuse core modules). Curricula can be added from a folder, a private overlay, or a separate git repository.
- Practice problems for Python, C++, and Rust with hidden tests, hints, follow-up stages, and measured space limits.
- Whiteboard rep tracker with FSRS scheduling, a due queue, and a self-score history.
- Study planner, readiness by level, and weak-area tracking.
- Local data directory with consistent rotating backups, a macOS login-item service, and an optional AI mock interviewer (bring your own API key).
- Each lesson shows `verified <date>` or `unverified draft`. Most lessons are currently unverified drafts.
- Maintenance tooling: course integrity checks, generated docs, scaffolds, and a default-deny publish check.

Known limitations: lessons have not had a systematic accuracy review; some planned modules are placeholders; the UI loads libraries from public CDNs; Windows is supported only through WSL.
