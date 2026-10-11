# Maintaining the course: adding and updating over time

The course is a set of Markdown lessons under `src/drillpad/content/modules/`, ordered by
`src/drillpad/content/paths.yaml`. It should grow in small, checked steps and never need a rewrite.
`scripts/course.py` does the bookkeeping so counts, docs, and ordering cannot drift.

```
python scripts/course.py check        # integrity + freshness (also runs in the test suite)
python scripts/course.py report       # thin lessons, open [VERIFY] tags, stale or unverified lessons
python scripts/course.py docs         # regenerate counts/tables in TRACKS.md and START_HERE.md
python scripts/course.py new-lesson MODULE SLUG "Title"
python scripts/course.py new-module ID STAGE "Title"
```

## Rules that keep it safe

1. **Append, never overwrite.** New lessons get the next number in their module. Existing lesson files are only
   edited to correct or refresh them, in their own commit, with the reason in the message. Never rename a module
   or lesson id: progress, whiteboard history, and Anki cards key off those ids.
2. **One change, one commit.** A lesson, its `module.yaml` entry, and the regenerated docs go in one signed commit.
   Do not batch a week of content into one commit and never squash a project's history.
3. **Evidence over assertion.** Numbers in lessons are either derived on the page from stated assumptions or sourced
   (paper, RFC, vendor docs) and tagged `[VERIFY]` until checked. Benchmark numbers about your own projects come only
   from `pow run` captures in `results/`, with the hardware named.
4. **Tests gate the merge.** `uv run pytest -q tests/test_course_docs.py tests/test_paths.py tests/test_web.py`
   must pass. `test_course_docs.py` fails if a module is unplaced, a lesson file is orphaned from its `module.yaml`,
   or `TRACKS.md` / `START_HERE.md` counts are stale.

## Add a lesson to an existing module

1. `python scripts/course.py new-lesson database-fundamentals query-planning "Query Planning and Joins"`
   creates the file from the lesson template and appends a `status: draft` entry to the module's `module.yaml`.
2. Write it to the lesson standard below. Run every code example you include and say how.
3. `python scripts/course.py docs && python scripts/course.py check`, then the tests.
4. Set `status: complete` in the module entry only after the checklist below passes.
5. Commit (signed) and add a journal line: `pow log "added <lesson>: why it was missing, what was checked"`.

## Add a curriculum (a focused track)

See `docs/CURRICULA.md`. In short: `new-curriculum` creates the track, list its planned modules in `curriculum.yaml`, then write them with
`new-module KEY --curriculum ID` and `new-lesson ID.KEY ...`. Reuse core modules with `uses:` instead of copying them.

## Add a module

1. Search first: `grep -ril "<topic>" src/drillpad/content/modules`. Prefer extending an existing module.
2. `python scripts/course.py new-module my-module 6-ai-infrastructure "My Module"` creates it and places it in a stage.
   If it has prerequisites, add them under `requires:` in `paths.yaml`; add it to a role path if it belongs there.
3. Add lessons as above, then `docs` and `check`.

## Lesson standard (definition of done)

- Sections in this order: the problem and why it matters; first principles; how it works with at least 2 ASCII
  diagrams; a worked failure scenario; a tradeoff table; interview questions with probing follow-ups and a worked
  exercise; a 5-item checklist; common wrong answers; related lessons.
- 6 to 12 KB. Under 4 KB is a stub (`course.py report` lists them).
- Every code block has a language tag and has been run, or is labeled pseudocode, or carries `[VERIFY - not executed]`.
- Service limits, hardware specs, prices, and version-specific behavior are `[VERIFY]` until checked against the
  primary source, then the tag is removed and `Last verified: YYYY-MM-DD` is updated.
- A `Drafted: YYYY-MM-DD (not yet verified)` line near the top when first written, replaced by `Last verified: YYYY-MM-DD`
  only after you have checked the lesson against primary sources. Never stamp a lesson verified because it was just written.
- Linked to neighbors by id (`module/lesson`) instead of repeating them.

## Keeping it current (cadence)

| When | What | Time |
|---|---|---|
| After every interview | Write down what you were asked and could not answer. Either fix a lesson, add a lesson, or add a line to your backlog of known gaps. Log whiteboard sessions for anything you drew. | 15 min |
| Weekly | `course.py report`. Pick the oldest or most-tagged lessons and verify a few against primary sources. Update `Last verified`. | 30 min |
| When a tool or model you rely on ships a release | Re-check the tool-specific lessons (`ai-augmented-engineering` 03, 04, 10; `llm-inference-systems`; `ai-platform-orchestration`). Delete advice the tools now handle. | 30 min |
| Quarterly | Re-read `paths.yaml`: is the order still the best learning order? Remove or merge lessons you never use. | 1 h |

Fast-moving material (tool mechanics, hardware, pricing, service limits) goes stale in months, principles in years.
Use `report --stale-days 60` for the fast-moving modules.

## Reviewing AI-drafted content

Most lessons were drafted by AI models. Treat a lesson as unreviewed until a human or a stronger model has checked it
and set `Last verified`. When delegating drafting to an agent, give it these rules: append-only; never overwrite;
number from the live module list; run code examples; tag unverified claims `[VERIFY]`; report every tag; do not commit.
Then review the diff before committing. The README's "How this was built" section must keep saying this accurately.

## Using the whiteboard tracker

Each lesson in the Learn page has a **Whiteboard** panel and each lesson row in the nav has a small square:
empty (never practiced), blue (practiced), amber (due now).

1. Read the lesson, close it, and draw the mechanism from memory (diagram, failure scenario, tradeoffs) while
   explaining out loud, as in an interview. Time-box it.
2. Score yourself honestly: **1** blank, **2** shaky, **3** got there with gaps, **4** solid, **5** flawless, cold.
   Add a note on what tripped you up. If you whiteboarded earlier, change the date before scoring.
3. The lesson comes back on a spaced schedule (FSRS). Scores of 3 or lower return in about a day, and repeated 4s and 5s
   stretch out toward a 45-day cap. The **Whiteboard queue** button at the top of the nav lists what is due.
4. A mistaken entry can be deleted with the x; the schedule is rebuilt from the remaining sessions.

Settings (target retention 0.95, 45-day cap) live at the top of `src/drillpad/web/whiteboard.py`.
Whiteboard data is stored in the local `drillpad.db` (table `whiteboard_sessions`).

## Where your data lives

Personal data never lives in the repository. `uv run drillpad paths` prints the locations; on macOS:

```
~/Library/Application Support/drillpad/
    drillpad.db     progress, practice attempts, whiteboard log
    backups/        rotating snapshots (latest 30), taken at startup and every 6 hours when the db changed
    private/        optional overlay (see below)
```

- Backups use SQLite's online backup, so they are consistent even if the app is writing. They are never committed to git.
- Set `DRILLPAD_BACKUP_DIR` (for example a folder in iCloud Drive) for a second copy of each snapshot. Re-run
  `drillpad service install` after setting it so the login item picks it up.
- Overrides: `DRILLPAD_DATA_DIR`, `DRILLPAD_DB`, `DRILLPAD_PRIVATE_DIR`. Tests always run against a temp directory.
- A `drillpad.db` left in the repo folder from before this change is an old copy. It is ignored by git and no longer used.
  Archive it once you trust the data directory copy.
- Time Machine already covers `~/Library/Application Support`, but a second, cloud-synced copy via `DRILLPAD_BACKUP_DIR` is
  worth having.

## Running without a terminal (macOS)

```
uv run drillpad service install     # login item: starts at login, restarts if it crashes
uv run drillpad service status
uv run drillpad service uninstall   # data is untouched
```

Bookmark `http://127.0.0.1:8765/learn`. The server listens on localhost only. It runs from the working tree, so a code or
lesson change shows up after `launchctl kickstart -k gui/$(id -u)/com.drillpad.serve`. Log: `~/Library/Logs/drillpad.log`.
If you change dependencies, run `uv sync` first because the login item does not sync.

## Private overlay (material that must not ship)

Put anything personal or firm-specific under `<data dir>/private/` instead of the repo:

```
private/modules/<module-id>/module.yaml + lessons/*.md    appears in Learn under "Private (local only)"
private/firms/<firm>.yaml                                  extra or overriding firm profiles
private/publish-banned.txt                                 one regex per line (names, employers) a maintainer's publish check enforces
```

Overlay modules get progress and whiteboard tracking like any other. A private module id that matches a bundled one is
ignored. Private firm profiles override bundled ones with the same id.
