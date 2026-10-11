"""Run the local web UI as a macOS login item (LaunchAgent), so a bookmark works without a terminal.

    drillpad service install     write the plist and start it now (and at every login)
    drillpad service status      is it loaded, and is the port answering
    drillpad service uninstall   stop it and remove the plist (your data is untouched)

The agent runs `uv run --no-sync --project <repo> drillpad serve`. It binds 127.0.0.1 only, restarts if it
crashes, and writes its log to ~/Library/Logs/drillpad.log. Any DRILLPAD_* variables set when you run `install` are
copied into the agent. After changing dependencies run `uv sync` yourself, and re-run `install` after changing those variables.
"""

import os
import plistlib
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

LABEL = "com.drillpad.serve"
PORT = 8765
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG = Path.home() / "Library" / "Logs" / "drillpad.log"


def build_plist(uv: str, project: Path, port: int = PORT, log: Path = LOG, extra_env: dict[str, str] | None = None) -> dict:
    env = {"PATH": f"{Path(uv).parent}:/usr/local/bin:/usr/bin:/bin", "HOME": str(Path.home())}
    env.update({k: v for k, v in (extra_env or {}).items() if k.startswith("DRILLPAD_")})
    return {
        "Label": LABEL,
        "ProgramArguments": [uv, "run", "--no-sync", "--project", str(project), "drillpad", "serve", "--port", str(port)],
        "WorkingDirectory": str(project),
        "EnvironmentVariables": env,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 15,
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
    }


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=False)


def answering(port: int = PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/modules", timeout=3) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def install(project: Path, port: int = PORT) -> int:
    if sys.platform != "darwin":
        print("service install is macOS only (uses launchd).")
        return 1
    uv = shutil.which("uv")
    if not uv:
        print("uv not found on PATH; install it first (https://docs.astral.sh/uv/).")
        return 1
    if answering(port) and _launchctl("print", f"{_domain()}/{LABEL}").returncode != 0:
        print(f"Something else is already serving on 127.0.0.1:{port}; stop it first or pick another port.")
        return 1
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_bytes(plistlib.dumps(build_plist(uv, project, port, extra_env=dict(os.environ))))
    _launchctl("bootout", f"{_domain()}/{LABEL}")  # replace a previous install cleanly; fine if absent
    out = _launchctl("bootstrap", _domain(), str(PLIST))
    if out.returncode != 0:
        print("launchctl bootstrap failed:", out.stderr.strip() or out.stdout.strip())
        return 1
    print(f"installed {PLIST}\nlog: {LOG}\nbookmark: http://127.0.0.1:{port}/learn")
    return 0


def status(port: int = PORT) -> int:
    loaded = _launchctl("print", f"{_domain()}/{LABEL}").returncode == 0
    print(f"launchd job {LABEL}: {'loaded' if loaded else 'not loaded'}")
    print(f"plist: {PLIST} ({'present' if PLIST.exists() else 'missing'})")
    print(f"http://127.0.0.1:{port}: {'answering' if answering(port) else 'not answering'}")
    return 0 if loaded else 1


def uninstall() -> int:
    _launchctl("bootout", f"{_domain()}/{LABEL}")
    PLIST.unlink(missing_ok=True)
    print("removed the login item; your data directory was not touched.")
    return 0
