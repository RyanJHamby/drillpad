"""Where drillpad keeps user data. Everything personal lives here, outside the source tree.

Layout (macOS shown; Linux uses $XDG_DATA_HOME or ~/.local/share, Windows %APPDATA%):

    ~/Library/Application Support/drillpad/
        drillpad.db        progress, attempts, whiteboard log
        backups/           rotating consistent snapshots of the db
        private/           optional overlay: modules/ and firms/ that never ship in the repo

Overrides: DRILLPAD_DATA_DIR (the whole directory), DRILLPAD_DB (just the database file),
DRILLPAD_PRIVATE_DIR (just the overlay), DRILLPAD_BACKUP_DIR (an extra offsite copy of each backup).
"""

import os
import shutil
import sys
from pathlib import Path


def data_dir() -> Path:
    env = os.environ.get("DRILLPAD_DATA_DIR")
    if env:
        return Path(env).expanduser()
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "drillpad"


def db_path() -> Path:
    env = os.environ.get("DRILLPAD_DB")
    return Path(env).expanduser() if env else data_dir() / "drillpad.db"


def backup_dir(db_file: Path | None = None) -> Path:
    return (db_file.parent if db_file else data_dir()) / "backups"


def offsite_backup_dir() -> Path | None:
    env = os.environ.get("DRILLPAD_BACKUP_DIR")
    return Path(env).expanduser() if env else None


def private_dir() -> Path:
    env = os.environ.get("DRILLPAD_PRIVATE_DIR")
    return Path(env).expanduser() if env else data_dir() / "private"


def migrate_legacy_db(target: Path, legacy: Path | None = None) -> bool:
    """One-time copy of a pre-data-dir ./drillpad.db to `target`. Never deletes or overwrites anything."""
    legacy = legacy or Path("drillpad.db")
    if target.exists() or not legacy.is_file():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, target)
    return True
