"""Shared utilities — safe subprocess, sudo helpers, git clone abstraction."""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from toolkit.ui import LOG_FILE, log, log_err, log_info, log_ok, log_warn


class SudoError(RuntimeError):
    """Raised when sudo access cannot be obtained."""


class CommandError(RuntimeError):
    """Raised when a subprocess command fails, carrying stderr."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Command failed (rc={returncode}): {shlex.join(cmd)}")


IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"

# ── Subprocess wrapper ───────────────────────────────────────────────────

def run_cmd(
    cmd: list[str],
    *,
    sudo: bool = False,
    capture: bool = True,
    check: bool = True,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = 300,
) -> subprocess.CompletedProcess[str]:
    """Run a command safely via subprocess.

    - When *sudo* is True on Linux, ``sudo`` is prepended.
    - On Windows, *sudo* is silently ignored.
    - stdout/stderr are always captured (unless *capture* is False) and
      appended to the log file.
    - If *check* is True and the command fails, a `CommandError` is raised
      with captured stderr for the caller to present to the user.
    """
    if sudo and IS_LINUX:
        cmd = ["sudo"] + cmd

    log(f"$ {shlex.join(cmd)}")

    merged_env: dict[str, str] | None = None
    if env:
        merged_env = {**os.environ, **env}

    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            input=input_text,
            env=merged_env,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise CommandError(cmd, 127, f"Command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        raise CommandError(cmd, -1, f"Command timed out after {timeout}s")

    # Append output to the log file
    if capture:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            if result.stdout:
                f.write(result.stdout)
            if result.stderr:
                f.write(result.stderr)

    if check and result.returncode != 0:
        stderr = result.stderr or "" if capture else ""
        raise CommandError(cmd, result.returncode, stderr)

    return result


# ── Privilege helpers ─────────────────────────────────────────────────────

def require_sudo() -> None:
    """Verify that sudo access is available.  Raises SudoError on failure."""
    if IS_WINDOWS:
        return
    try:
        run_cmd(["sudo", "-v"], check=True, capture=True, timeout=30)
    except (CommandError, Exception) as exc:
        raise SudoError(
            "sudo access is required. Please configure sudo for your user."
        ) from exc


def check_not_root() -> bool:
    """Warn if running as root.  Returns True if the user wants to continue."""
    if IS_WINDOWS or os.geteuid() != 0:  # type: ignore[attr-defined]
        return True
    log_warn("This script should NOT be run as root.")
    log_warn("AUR helpers (yay/paru) refuse to run as root.")
    log_warn("Only individual commands will be elevated with sudo.")
    from toolkit.ui import confirm
    return confirm("Continue anyway?")


# ── Git clone abstraction ─────────────────────────────────────────────────

def _extract_github_slug(url: str) -> str | None:
    """Return 'owner/repo' from a GitHub URL, or None."""
    import re
    m = re.match(r"^https://github\.com/([^/]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def gh_clone(url: str, dest: str | Path, *, sudo: bool = False) -> bool:
    """Clone a repo, preferring the ``gh`` CLI for authenticated access.

    Falls back to ``git clone --depth 1``.  When *sudo* is True, clone
    to a temp directory then move (avoids running git/gh as root).
    Returns True on success.
    """
    dest = Path(dest)
    slug = _extract_github_slug(url)

    # ── Try gh CLI first ──
    if slug and shutil.which("gh"):
        log(f"Cloning via gh: {slug} → {dest}")
        try:
            if sudo:
                with tempfile.TemporaryDirectory(prefix="ghclone_") as tmp:
                    repo_dir = Path(tmp) / "repo"
                    run_cmd(["gh", "repo", "clone", slug, str(repo_dir), "--", "--depth", "1"])
                    run_cmd(["rm", "-rf", str(dest)], sudo=True, check=False)
                    run_cmd(["mv", str(repo_dir), str(dest)], sudo=True)
                return True
            else:
                run_cmd(["gh", "repo", "clone", slug, str(dest), "--", "--depth", "1"])
                return True
        except CommandError:
            log_warn("gh clone failed — falling back to git.")

    # ── Fallback: git clone ──
    if not shutil.which("git"):
        log_err("Neither gh nor git found.  Cannot clone.")
        return False

    try:
        if sudo:
            with tempfile.TemporaryDirectory(prefix="gitclone_") as tmp:
                repo_dir = Path(tmp) / "repo"
                run_cmd(["git", "clone", "--depth", "1", url, str(repo_dir)])
                run_cmd(["rm", "-rf", str(dest)], sudo=True, check=False)
                run_cmd(["mv", str(repo_dir), str(dest)], sudo=True)
            return True
        else:
            run_cmd(["git", "clone", "--depth", "1", url, str(dest)])
            return True
    except CommandError:
        log_err(f"git clone failed for {url}")
        return False
