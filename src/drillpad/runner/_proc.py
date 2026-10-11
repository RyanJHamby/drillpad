"""Shared subprocess helper for compiled-language runners (rlimits, timeout, scrubbed env)."""

import os
import resource
import subprocess
import sys
from pathlib import Path

CPU_SECONDS = 20


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))


def toolchain_env() -> dict[str, str]:
    """Environment for invoking compilers (needs HOME for rustup shims)."""
    home = str(Path.home())
    return {"PATH": f"/usr/bin:/bin:{home}/.cargo/bin", "HOME": home}


def run_cmd(cmd: list[str], cwd: str, timeout_s: float, env: dict[str, str], stdin: str = "") -> tuple[int | None, str, str, bool]:
    """Returns (returncode, stdout, stderr, timed_out)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, input=stdin, capture_output=True, text=True, timeout=timeout_s,
                           preexec_fn=_limits, check=False, errors="replace")
        return p.returncode, p.stdout, p.stderr, False
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return None, out, "timed out", True


def scrubbed_env() -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin"}


def have(tool: str) -> bool:
    env = toolchain_env()
    return any(os.access(os.path.join(d, tool), os.X_OK) for d in env["PATH"].split(":"))
