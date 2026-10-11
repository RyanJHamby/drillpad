import plistlib

from drillpad import service


def test_launch_agent_plist(tmp_path):
    project = tmp_path / "proj"
    p = plistlib.loads(plistlib.dumps(service.build_plist("/opt/bin/uv", project, 8765, tmp_path / "log")))
    assert p["Label"] == "com.drillpad.serve" and p["RunAtLoad"] and p["KeepAlive"]
    assert p["ProgramArguments"] == ["/opt/bin/uv", "run", "--no-sync", "--project", str(project), "drillpad", "serve", "--port", "8765"]
    assert p["WorkingDirectory"] == str(project) and p["StandardOutPath"] == str(tmp_path / "log")
    assert p["EnvironmentVariables"]["PATH"].startswith("/opt/bin:")


def test_only_drillpad_env_vars_are_passed_through(tmp_path):
    env = {"DRILLPAD_BACKUP_DIR": "/x/icloud", "DRILLPAD_DB": "/x/db", "AWS_SECRET_ACCESS_KEY": "nope", "HOME": "/evil"}
    p = service.build_plist("/opt/bin/uv", tmp_path, 8765, tmp_path / "log", extra_env=env)
    out = p["EnvironmentVariables"]
    assert out["DRILLPAD_BACKUP_DIR"] == "/x/icloud" and out["DRILLPAD_DB"] == "/x/db"
    assert "AWS_SECRET_ACCESS_KEY" not in out and out["HOME"] != "/evil"
