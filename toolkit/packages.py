"""Cross-platform package manager abstraction.

Routes install / remove / query operations through the detected
system package manager (apt, dnf, pacman+AUR, winget, choco).
"""

from __future__ import annotations

import os

from toolkit.detection import SystemDetect
from toolkit.ui import log, log_err, log_ok
from toolkit.util import IS_LINUX, IS_WINDOWS, CommandError, run_cmd


class PackageManager:
    """Thin wrapper that delegates to the system's native package manager."""

    def __init__(self, system: SystemDetect) -> None:
        self.system = system

    # ── Public API ────────────────────────────────────────────────────

    def install(self, *pkgs: str) -> bool:
        """Install one or more packages.  Returns True on success."""
        if not pkgs:
            return True
        pkg_list = list(pkgs)
        log(f"Installing: {' '.join(pkg_list)}")

        try:
            match self.system.distro_family:
                case "debian":
                    run_cmd(["apt-get", "update", "-qq"], sudo=True)
                    run_cmd(["apt-get", "install", "-y", *pkg_list], sudo=True)
                case "fedora":
                    run_cmd(["dnf", "install", "-y", *pkg_list], sudo=True)
                case "arch":
                    self._arch_install(pkg_list)
                case _:
                    if IS_WINDOWS:
                        return self._windows_install(pkg_list)
                    log_err(f"No package manager for family '{self.system.distro_family}'")
                    return False
            return True
        except CommandError as exc:
            log_err(f"Package installation failed: {exc.stderr[:300]}")
            return False

    def remove(self, *pkgs: str) -> bool:
        """Remove one or more packages.  Returns True on success."""
        if not pkgs:
            return True
        pkg_list = list(pkgs)
        log(f"Removing: {' '.join(pkg_list)}")

        try:
            match self.system.distro_family:
                case "debian":
                    run_cmd(["apt-get", "remove", "-y", *pkg_list], sudo=True, check=False)
                case "fedora":
                    run_cmd(["dnf", "remove", "-y", *pkg_list], sudo=True, check=False)
                case "arch":
                    run_cmd(["pacman", "-Rns", "--noconfirm", *pkg_list], sudo=True, check=False)
                case _:
                    log_err("Package removal not supported on this platform.")
                    return False
            return True
        except CommandError as exc:
            log_err(f"Package removal failed: {exc.stderr[:300]}")
            return False

    def is_installed(self, pkg: str) -> bool:
        """Check whether a single package is installed."""
        try:
            match self.system.distro_family:
                case "debian":
                    run_cmd(["dpkg", "-s", pkg], check=True)
                case "fedora":
                    run_cmd(["rpm", "-q", pkg], check=True)
                case "arch":
                    run_cmd(["pacman", "-Qi", pkg], check=True)
                case _:
                    return False
            return True
        except CommandError:
            return False

    def update_cache(self) -> None:
        """Refresh the local package index (where applicable)."""
        try:
            match self.system.distro_family:
                case "debian":
                    run_cmd(["apt-get", "update", "-qq"], sudo=True)
                case "fedora":
                    run_cmd(["dnf", "check-update"], sudo=True, check=False)
                case "arch":
                    run_cmd(["pacman", "-Syy", "--noconfirm"], sudo=True)
        except CommandError:
            pass

    # ── Private helpers ───────────────────────────────────────────────

    def _arch_install(self, pkgs: list[str]) -> None:
        """Install via AUR helper (preferred) or pacman."""
        is_root = hasattr(os, "geteuid") and os.geteuid() == 0
        if self.system.aur_helper and not is_root:
            run_cmd([self.system.aur_helper, "-S", "--needed", "--noconfirm", *pkgs])
        else:
            run_cmd(["pacman", "-S", "--needed", "--noconfirm", *pkgs], sudo=True)

    def _windows_install(self, pkgs: list[str]) -> bool:
        """Best-effort install via winget or choco on Windows."""
        mgr = self.system.pkg_manager
        if not mgr:
            log_err("No Windows package manager available (install winget or chocolatey).")
            return False
        try:
            for pkg in pkgs:
                if mgr == "winget":
                    run_cmd(["winget", "install", "--accept-package-agreements",
                             "--accept-source-agreements", "-e", "--id", pkg])
                elif mgr == "choco":
                    run_cmd(["choco", "install", "-y", pkg])
            return True
        except CommandError as exc:
            log_err(f"Windows package install failed: {exc.stderr[:300]}")
            return False
