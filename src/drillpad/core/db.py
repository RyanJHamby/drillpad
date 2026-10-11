import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY,
  problem_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  finished_at TEXT,
  outcome TEXT
);
-- Append-only: triggers below block UPDATE/DELETE so history doubles as an audit log.
CREATE TABLE IF NOT EXISTS revisions (
  id INTEGER PRIMARY KEY,
  attempt_id INTEGER NOT NULL REFERENCES attempts(id),
  seq INTEGER NOT NULL,
  code TEXT NOT NULL,
  passed INTEGER NOT NULL,
  results_json TEXT NOT NULL,
  elapsed_ms INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE(attempt_id, seq)
);
CREATE TRIGGER IF NOT EXISTS revisions_no_update BEFORE UPDATE ON revisions
BEGIN SELECT RAISE(ABORT, 'revisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS revisions_no_delete BEFORE DELETE ON revisions
BEGIN SELECT RAISE(ABORT, 'revisions are append-only'); END;
"""

# Migration 2 (append-only addition): per-attempt weakness tags. Existing tables/triggers untouched.
# severity: 1 (minor) .. 3 (major). category: pattern|language|algorithm|problem|communication.
WEAKNESS_SCHEMA = """
CREATE TABLE IF NOT EXISTS weakness_events (
  id INTEGER PRIMARY KEY,
  attempt_id INTEGER NOT NULL REFERENCES attempts(id),
  category TEXT NOT NULL,
  tag TEXT NOT NULL,
  severity INTEGER NOT NULL DEFAULT 1 CHECK (severity BETWEEN 1 AND 3),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS weakness_events_tag ON weakness_events(category, tag);
"""
SCHEMA += WEAKNESS_SCHEMA

# ---- Migration 3 (append-only addition): text interview mode. No secrets are ever stored here. ----
# interview_sessions is mutable only for finish-time fields; interview_events is append-only.
INTERVIEW_SCHEMA = """
CREATE TABLE IF NOT EXISTS interview_sessions (
  id INTEGER PRIMARY KEY,
  problem_id TEXT NOT NULL,
  format TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  finished_at TEXT,
  hints_used INTEGER NOT NULL DEFAULT 0,
  usage_json TEXT,
  est_cost_usd REAL,
  summary_json TEXT
);
CREATE TABLE IF NOT EXISTS interview_events (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES interview_sessions(id),
  seq INTEGER NOT NULL,
  role TEXT NOT NULL,
  kind TEXT NOT NULL,
  content TEXT NOT NULL DEFAULT '',
  elapsed_min REAL,
  meta_json TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE(session_id, seq)
);
CREATE TRIGGER IF NOT EXISTS interview_events_no_update BEFORE UPDATE ON interview_events
BEGIN SELECT RAISE(ABORT, 'interview_events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS interview_events_no_delete BEFORE DELETE ON interview_events
BEGIN SELECT RAISE(ABORT, 'interview_events are append-only'); END;
"""
SCHEMA += INTERVIEW_SCHEMA


def migrate_add_weakness_events(conn: sqlite3.Connection) -> None:
    """Idempotent migration: create weakness_events on a DB opened without connect()."""
    conn.executescript(WEAKNESS_SCHEMA)


class _Result:
    """Fully materialised query result, so callers never touch a live cursor outside the lock."""

    def __init__(self, rows, lastrowid, rowcount):
        self._rows, self.lastrowid, self.rowcount = rows, lastrowid, rowcount

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class LockedConnection:
    """sqlite3 connection shared by FastAPI's worker threads: every statement runs under one RLock.

    A bare shared connection raised InterfaceError and raced on MAX(seq)+1 under concurrent requests.
    Use `with conn.lock:` around multi-statement read-modify-write sequences.
    """

    def __init__(self, raw: sqlite3.Connection):
        self._raw = raw
        self.lock = threading.RLock()

    def execute(self, sql, params=()):
        with self.lock:
            cur = self._raw.execute(sql, params)
            rows = cur.fetchall() if cur.description else []
            return _Result(rows, cur.lastrowid, cur.rowcount)

    def executescript(self, script):
        with self.lock:
            return self._raw.executescript(script)

    def commit(self):
        with self.lock:
            self._raw.commit()

    def close(self):
        with self.lock:
            self._raw.close()


def connect(path: str | Path = "drillpad.db", **kw) -> LockedConnection:
    kw.setdefault("check_same_thread", False)
    raw = sqlite3.connect(path, **kw)
    raw.row_factory = sqlite3.Row
    raw.executescript(SCHEMA)
    cols = {r["name"] for r in raw.execute("PRAGMA table_info(revisions)")}
    if "active_ms" not in cols:  # migrate DBs created before the active-time clock existed
        raw.execute("ALTER TABLE revisions ADD COLUMN active_ms INTEGER")
        raw.commit()
    return LockedConnection(raw)


def start_attempt(conn: sqlite3.Connection, problem_id: str, mode: str = "practice") -> int:
    cur = conn.execute("INSERT INTO attempts(problem_id, mode) VALUES (?, ?)", (problem_id, mode))
    conn.commit()
    return cur.lastrowid


def add_revision(
    conn: sqlite3.Connection, attempt_id: int, code: str, passed: bool, results_json: str, elapsed_ms: int,
    active_ms: int | None = None,
) -> int:
    with conn.lock:  # read-modify-write must be atomic across request threads
        seq = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM revisions WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO revisions(attempt_id, seq, code, passed, results_json, elapsed_ms, active_ms) VALUES (?,?,?,?,?,?,?)",
            (attempt_id, seq, code, int(passed), results_json, elapsed_ms, active_ms),
        )
        conn.commit()
    return seq


def revisions(conn: sqlite3.Connection, attempt_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM revisions WHERE attempt_id = ? ORDER BY seq", (attempt_id,)
    ).fetchall()


EVALUATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluations (
  id INTEGER PRIMARY KEY,
  attempt_id INTEGER NOT NULL REFERENCES attempts(id),
  problem_id TEXT NOT NULL,
  dims_json TEXT NOT NULL,         -- 0..1 per dimension, null = not assessed
  detail_json TEXT NOT NULL,       -- edge-by-tag, complexity per op, pace, ...
  submissions_json TEXT NOT NULL,  -- what the user submitted (complexity answers, extension answers)
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TRIGGER IF NOT EXISTS evaluations_no_update BEFORE UPDATE ON evaluations
BEGIN SELECT RAISE(ABORT, 'evaluations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS evaluations_no_delete BEFORE DELETE ON evaluations
BEGIN SELECT RAISE(ABORT, 'evaluations are append-only'); END;
"""
SCHEMA += EVALUATION_SCHEMA


SOLUTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS solution_views (
  id INTEGER PRIMARY KEY,
  attempt_id INTEGER NOT NULL REFERENCES attempts(id),
  reason TEXT NOT NULL,            -- 'passed' | 'stuck'
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TRIGGER IF NOT EXISTS solution_views_no_update BEFORE UPDATE ON solution_views
BEGIN SELECT RAISE(ABORT, 'solution_views are append-only'); END;
CREATE TRIGGER IF NOT EXISTS solution_views_no_delete BEFORE DELETE ON solution_views
BEGIN SELECT RAISE(ABORT, 'solution_views are append-only'); END;
"""
SCHEMA += SOLUTION_SCHEMA


PLAN_SCHEMA = """
CREATE TABLE IF NOT EXISTS plan_settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  settings_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""
SCHEMA += PLAN_SCHEMA


SRS_SCHEMA = """
CREATE TABLE IF NOT EXISTS srs_cards (            -- current FSRS state per problem (mutable)
  problem_id TEXT PRIMARY KEY,
  card_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS srs_reviews (          -- append-only review log, one per attempt
  id INTEGER PRIMARY KEY,
  problem_id TEXT NOT NULL,
  attempt_id INTEGER NOT NULL UNIQUE,
  ease INTEGER NOT NULL,                          -- 1 Again .. 4 Easy
  source TEXT NOT NULL,                           -- 'pass' | 'stuck'
  reviewed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TRIGGER IF NOT EXISTS srs_reviews_no_update BEFORE UPDATE ON srs_reviews
BEGIN SELECT RAISE(ABORT, 'srs_reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS srs_reviews_no_delete BEFORE DELETE ON srs_reviews
BEGIN SELECT RAISE(ABORT, 'srs_reviews are append-only'); END;
"""
SCHEMA += SRS_SCHEMA


DRAFT_SCHEMA = """
CREATE TABLE IF NOT EXISTS drafts (               -- latest editor contents per problem (mutable autosave)
  problem_id TEXT PRIMARY KEY,
  code TEXT NOT NULL,
  attempt_id INTEGER,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""
SCHEMA += DRAFT_SCHEMA


CLOCK_SCHEMA = """
CREATE TABLE IF NOT EXISTS attempt_clock (        -- active (un-paused) time per attempt, in ms; monotonic
  attempt_id INTEGER PRIMARY KEY,
  active_ms INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""
SCHEMA += CLOCK_SCHEMA


LESSON_SCHEMA = """
CREATE TABLE IF NOT EXISTS lesson_progress (      -- which lessons the user has marked done
  module_id TEXT NOT NULL,
  lesson_id TEXT NOT NULL,
  done_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY (module_id, lesson_id)
);
"""
SCHEMA += LESSON_SCHEMA

WHITEBOARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS whiteboard_sessions (  -- self-scored whiteboard practice per lesson (1-5)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  module_id TEXT NOT NULL,
  lesson_id TEXT NOT NULL,
  score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_whiteboard_lesson ON whiteboard_sessions(module_id, lesson_id, created_at);
"""
SCHEMA += WHITEBOARD_SCHEMA
