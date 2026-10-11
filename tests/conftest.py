import pytest


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Never let a test read or write the real user data directory, overlay, or offsite backup folder."""
    for var in ("DRILLPAD_DB", "DRILLPAD_PRIVATE_DIR", "DRILLPAD_BACKUP_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DRILLPAD_DATA_DIR", str(tmp_path / "data-dir"))
