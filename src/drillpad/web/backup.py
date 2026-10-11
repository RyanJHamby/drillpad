"""Local database backups: consistent SQLite snapshots with rotation and an optional offsite copy.

Backups never touch git. The database holds personal practice history, so it must not end up in a repo.
Set DRILLPAD_BACKUP_DIR (for example a folder in iCloud Drive or a synced drive) for a second copy of each snapshot.
"""

import shutil
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from drillpad.core import paths

KEEP = 30
INTERVAL_SECONDS = 6 * 3600


def _snapshot(db_file: Path, dest: Path) -> None:
    """Copy via SQLite's online backup API so a write in flight can never produce a torn file."""
    tmp = dest.with_suffix(".tmp")
    src = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    tmp.replace(dest)


def _rotate(folder: Path, keep: int) -> None:
    for old in sorted(folder.glob("drillpad-*.db"))[:-keep]:
        old.unlink(missing_ok=True)


def backup_database(db_file: Path, backup_dir: Path | None = None, keep: int = KEEP,
                    offsite_dir: Path | None = None) -> Path | None:
    """Snapshot `db_file`. Returns the new backup path, or None if there is nothing new to back up."""
    if not db_file.exists():
        return None
    folder = backup_dir or paths.backup_dir(db_file)
    folder.mkdir(parents=True, exist_ok=True)
    latest = max(folder.glob("drillpad-*.db"), key=lambda p: p.stat().st_mtime, default=None)
    changed = max(p.stat().st_mtime for p in (db_file, db_file.with_name(db_file.name + "-wal")) if p.exists())
    if latest and latest.stat().st_mtime >= changed:
        return None  # no writes since the last snapshot
    dest = folder / f"drillpad-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f')}.db"
    _snapshot(db_file, dest)
    _rotate(folder, keep)
    extra = offsite_dir if offsite_dir is not None else paths.offsite_backup_dir()
    if extra:
        try:
            extra.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, extra / dest.name)
            _rotate(extra, keep)
        except OSError as e:  # an unplugged drive must not stop the app; the local snapshot already exists
            print(f"warning: offsite backup to {extra} failed: {e}")
    return dest


def start_periodic_backup(db_file: Path, interval_seconds: int = INTERVAL_SECONDS) -> threading.Event:
    """Back up every `interval_seconds` on a daemon thread (only writes when the db changed). Set the event to stop."""
    stop = threading.Event()

    def loop() -> None:
        while not stop.wait(interval_seconds):
            try:
                backup_database(db_file)
            except (OSError, sqlite3.Error) as e:
                print(f"warning: periodic backup failed: {e}")

    threading.Thread(target=loop, name="drillpad-backup", daemon=True).start()
    return stop
