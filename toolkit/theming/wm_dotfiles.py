"""WM dotfile fetcher — clone and apply community tiling WM configs.

Supports:
- ml4w dotfiles (Hyprland)
- JaKooLit Hyprland dotfiles
- Custom URL input
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from toolkit.detection import SystemDetect
from toolkit.packages import PackageManager
from toolkit.ui import (
    confirm,
    console,
    log,
    log_err,
    log_info,
    log_ok,
    log_warn,
    prompt,
    section,
    banner,
)
from toolkit.util import CommandError, gh_clone, run_cmd

_CONFIG_DIRS = (
    ".config/hypr",
    ".config/waybar",
    ".config/wofi",
    ".config/rofi",
    ".config/kitty",
    ".config/foot",
    ".config/sway",
    ".config/dunst",
    ".config/mako",
    ".config/wlogout",
)

DOT_REPOS = [
    {"name": "ml4w Dotfiles (Hyprland/Arch)", "repo": "https://github.com/mylinuxforwork/dotfiles.git", "has_installer": True},
    {"name": "JaKooLit Hyprland (Arch)",       "repo": "https://github.com/JaKooLit/Arch-Hyprland.git",  "has_installer": True},
    {"name": "JaKooLit Hyprland (Fedora)",     "repo": "https://github.com/JaKooLit/Fedora-Hyprland.git", "has_installer": True},
    {"name": "JaKooLit Hyprland (Debian/Ubuntu)", "repo": "https://github.com/JaKooLit/Debian-Hyprland.git", "has_installer": True},
]


class WMDotfiles:
    """Community WM dotfile fetcher and installer."""

    def __init__(self, system: SystemDetect, pkg: PackageManager) -> None:
        self.system = system
        self.pkg = pkg
        self.home = Path.home()

    def run(self) -> None:
        banner("WM / Tiling Dotfile Fetcher")
        console.print("  Fetch and install community dotfiles for tiling window managers.")
        console.print()

        for i, repo in enumerate(DOT_REPOS, 1):
            console.print(f"    {i}) {repo['name']}")
        console.print()
        console.print(f"    C) Clone from a custom Git URL")
        console.print(f"    0) Cancel")
        console.print()

        from rich.prompt import Prompt
        choice = Prompt.ask("  Enter choice", default="0").strip()

        if choice == "0":
            return
        if choice.upper() == "C":
            self._custom_clone()
            return

        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(DOT_REPOS)):
                raise ValueError
        except ValueError:
            console.print("  Invalid choice.")
            return

        repo_info = DOT_REPOS[idx]
        self._install_dots(repo_info["repo"], repo_info["name"], repo_info["has_installer"])

    def _install_dots(self, repo_url: str, label: str, has_installer: bool) -> None:
        if not shutil.which("git") and not shutil.which("gh"):
            log_err("git or gh CLI is required.")
            return

        log(f"Cloning: {label}")

        with tempfile.TemporaryDirectory(prefix="dots_") as tmpdir:
            if not gh_clone(repo_url, tmpdir):
                log_err("Failed to clone repository.")
                return
            log_ok("Repository cloned.")

            clone_path = Path(tmpdir)

            if has_installer:
                install_sh = clone_path / "install.sh"
                if install_sh.exists():
                    console.print()
                    console.print("  [bold]An install.sh script was found.[/bold]")
                    console.print("  This will run the upstream installer, which may install")
                    console.print("  packages and overwrite dotfiles.")
                    console.print()
                    if confirm("Run the upstream install script?"):
                        install_sh.chmod(0o755)
                        log("Running install.sh…")
                        run_cmd(["bash", str(install_sh)], check=False, capture=False)
                        log_ok(f"{label} installer completed.")
                        return

            # Manual copy fallback
            console.print()
            console.print("  Manual dotfile installation:")
            self._backup_and_copy(clone_path)

    def _custom_clone(self) -> None:
        console.print()
        url = prompt("Git repository URL (0 to cancel)")
        if url in ("0", ""):
            return
        self._install_dots(url, "Custom dotfiles", has_installer=True)

    def _backup_and_copy(self, source: Path) -> None:
        """Backup existing configs and copy new ones from source."""
        timestamp = f"{datetime.now():%Y%m%d_%H%M%S}"

        # Detect which config dirs exist in source
        found: list[tuple[Path, Path]] = []
        for rel in _CONFIG_DIRS:
            src = source / rel
            if not src.is_dir():
                # Also check without .config prefix (some repos use flat structure)
                flat = source / Path(rel).name
                if flat.is_dir():
                    src = flat
                else:
                    continue
            dest = self.home / rel
            found.append((src, dest))

        if not found:
            log_info("No recognized config directories found in the repo.")
            console.print("  The repo may use a custom structure. Check its README.")
            return

        console.print(f"  Found {len(found)} config directories to install:")
        for src, dest in found:
            status = "[yellow]exists[/yellow]" if dest.exists() else "[dim]new[/dim]"
            console.print(f"    • {dest.relative_to(self.home)}  ({status})")
        console.print()

        if not confirm("Proceed with backup and copy?"):
            return

        for src, dest in found:
            if dest.exists():
                bak = dest.with_name(f"{dest.name}.bak_{timestamp}")
                shutil.copytree(dest, bak)
                log_ok(f"Backed up {dest.name} → {bak.name}")
                shutil.rmtree(dest)

            shutil.copytree(src, dest)
            log_ok(f"Installed {dest.relative_to(self.home)}")

        log_ok("Dotfiles installed. Restart your WM session for changes to take effect.")
