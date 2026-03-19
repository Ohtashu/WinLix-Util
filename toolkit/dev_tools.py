"""Developer Tools & LazyVim Setup module.

Installs essential developer tools (git, gcc, node, ripgrep, etc.) and
sets up Neovim with the LazyVim starter configuration.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from toolkit.detection import SystemDetect
from toolkit.packages import PackageManager
from toolkit.ui import (
    banner,
    confirm,
    console,
    log,
    log_err,
    log_info,
    log_ok,
    log_warn,
    press_enter,
    section,
    status_icon,
)
from toolkit.util import CommandError, gh_clone, require_sudo, run_cmd


# Tool → package mapping per distro family
_TOOL_MAP: dict[str, dict[str, str]] = {
    "debian": {
        "git": "git", "curl": "curl", "wget": "wget",
        "gcc": "build-essential", "nodejs": "nodejs", "npm": "npm",
        "rg": "ripgrep", "fd": "fd-find", "unzip": "unzip",
    },
    "fedora": {
        "git": "git", "curl": "curl", "wget": "wget",
        "gcc": "gcc gcc-c++ make", "nodejs": "nodejs", "npm": "npm",
        "rg": "ripgrep", "fd": "fd-find", "unzip": "unzip",
    },
    "arch": {
        "git": "git", "curl": "curl", "wget": "wget",
        "gcc": "base-devel", "nodejs": "nodejs", "npm": "npm",
        "rg": "ripgrep", "fd": "fd", "unzip": "unzip",
    },
}

_TOOL_ORDER = ["git", "curl", "wget", "gcc", "nodejs", "npm", "rg", "fd", "unzip"]


class DevTools:
    """Developer essentials and LazyVim installer."""

    def __init__(self, system: SystemDetect, pkg: PackageManager) -> None:
        self.system = system
        self.pkg = pkg

    def run(self) -> None:
        banner("Module 4 — Developer Tools & LazyVim")
        console.print("  [bold]Select an option:[/bold]")
        console.print()
        console.print("    [cyan]1)[/cyan] Install Developer Essentials (git, gcc, node, ripgrep, …)")
        console.print("    [cyan]2)[/cyan] Neovim / LazyVim Setup")
        console.print("    [cyan]3)[/cyan] Both")
        console.print()
        console.print("    [dim]0)[/dim] Back to main menu")
        console.print()

        from rich.prompt import Prompt
        choice = Prompt.ask("  Enter choice", default="0").strip()

        match choice:
            case "1":
                self._install_essentials()
            case "2":
                self._setup_lazyvim()
            case "3":
                self._install_essentials()
                self._setup_lazyvim()
            case "0":
                return
            case _:
                console.print("  Invalid choice.")

        press_enter()

    # ── Developer Essentials ──────────────────────────────────────────

    def _install_essentials(self) -> None:
        section("Developer Essentials")

        tool_map = _TOOL_MAP.get(self.system.distro_family, {})
        if not tool_map:
            log_warn(f"No tool map for {self.system.distro_family}. Skipping.")
            return

        missing: list[str] = []
        for tool in _TOOL_ORDER:
            pkg = tool_map.get(tool, "")
            installed = shutil.which(tool) is not None
            icon = status_icon(installed)
            if installed:
                console.print(f"    {icon} {tool}")
            else:
                console.print(f"    {icon} {tool}  → {pkg}")
                missing.extend(pkg.split())

        console.print()
        if not missing:
            log_ok("All developer essentials are installed.")
        else:
            log_warn(f"Missing packages: {' '.join(missing)}")
            if confirm("Install missing developer tools?"):
                try:
                    require_sudo()
                except Exception:
                    return
                if self.pkg.install(*missing):
                    log_ok("Developer tools installed.")

    # ── LazyVim ───────────────────────────────────────────────────────

    def _setup_lazyvim(self) -> None:
        section("Neovim / LazyVim Setup")

        # Check / install Neovim
        if shutil.which("nvim"):
            try:
                result = run_cmd(["nvim", "--version"], check=False)
                ver = (result.stdout or "").splitlines()[0] if result.stdout else "unknown"
                log_ok(f"Neovim found: {ver}")
            except CommandError:
                log_ok("Neovim found.")
        else:
            log_warn("Neovim is not installed.")
            if not confirm("Install Neovim?"):
                return
            self.pkg.install("neovim")
            if not shutil.which("nvim"):
                log_err("Neovim installation failed or version is too old.")
                log_info("LazyVim requires Neovim >= 0.9. Consider installing from GitHub releases.")
                return
            log_ok("Neovim installed.")

        console.print()
        if not confirm("Set up LazyVim starter template?"):
            return

        if not shutil.which("git"):
            log_err("git is required for LazyVim. Install it first.")
            return

        # Back up existing config
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        home = Path.home()
        backup_dirs = [
            home / ".config" / "nvim",
            home / ".local" / "share" / "nvim",
            home / ".local" / "state" / "nvim",
            home / ".cache" / "nvim",
        ]

        backed_up = False
        for d in backup_dirs:
            if d.is_dir():
                backup = d.with_name(f"{d.name}.bak_{ts}")
                log(f"Backing up {d} → {backup}")
                d.rename(backup)
                backed_up = True
        if backed_up:
            log_ok("Existing Neovim configs backed up.")

        # Clone LazyVim starter
        log("Cloning LazyVim starter…")
        dest = home / ".config" / "nvim"
        if gh_clone("https://github.com/LazyVim/starter.git", dest):
            git_dir = dest / ".git"
            if git_dir.exists():
                shutil.rmtree(git_dir)
            log_ok("LazyVim starter installed to ~/.config/nvim")
            log_info("Run 'nvim' to complete the LazyVim bootstrap.")
        else:
            log_err("Failed to clone LazyVim starter — check the log file.")
