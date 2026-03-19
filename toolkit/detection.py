"""Cross-platform system detection.

Detects OS type, Linux distribution family, package manager, desktop
environment, display manager, and chassis type (laptop vs desktop).
"""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

from toolkit.ui import info_table, log_err, log_info, log_ok, section
from toolkit.util import IS_LINUX, IS_WINDOWS, CommandError, run_cmd


class SystemDetect:
    """Gather and cache system environment information."""

    def __init__(self) -> None:
        self.os_type: str = platform.system().lower()  # "linux" | "windows"
        self.distro_id: str = ""
        self.distro_pretty: str = ""
        self.distro_family: str = ""  # "arch" | "debian" | "fedora" | ""
        self.pkg_manager: str = ""    # "pacman" | "apt" | "dnf" | "winget" | "choco"
        self.aur_helper: str = ""     # "yay" | "paru" | ""
        self.current_de: str = ""
        self.current_dm: str = ""
        self.chassis_type: str = "unknown"  # "laptop" | "desktop" | "unknown"

    # ── Public entry point ────────────────────────────────────────────

    def detect_all(self) -> None:
        """Run all detection routines and display results."""
        section("Detecting System Environment")
        if IS_LINUX:
            self._detect_distro()
            self._detect_package_manager()
            self._detect_current_de()
            self._detect_current_dm()
            self._detect_chassis()
        elif IS_WINDOWS:
            self.distro_pretty = f"Windows {platform.version()}"
            self._detect_windows_pkg_manager()
            log_ok(f"OS: {self.distro_pretty}")
        else:
            self.distro_pretty = platform.platform()
            log_info(f"OS: {self.distro_pretty} (limited support)")

        self._show_summary()

    # ── Linux detection ───────────────────────────────────────────────

    def _detect_distro(self) -> None:
        os_release = Path("/etc/os-release")
        if not os_release.exists():
            log_err("Cannot find /etc/os-release — unable to detect distribution.")
            return

        data: dict[str, str] = {}
        for line in os_release.read_text().splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                data[key.strip()] = value.strip().strip('"')

        self.distro_id = data.get("ID", "").lower()
        self.distro_pretty = data.get("PRETTY_NAME", self.distro_id)
        id_like = data.get("ID_LIKE", "").lower()

        if self.distro_id == "arch" or "arch" in id_like:
            self.distro_family = "arch"
        elif self.distro_id in ("debian", "ubuntu") or any(
            d in id_like for d in ("debian", "ubuntu")
        ):
            self.distro_family = "debian"
        elif self.distro_id in ("fedora", "rhel", "centos") or any(
            d in id_like for d in ("fedora", "rhel")
        ):
            self.distro_family = "fedora"
        else:
            log_err(f"Unsupported distribution: {self.distro_pretty}")
            return

        log_ok(f"Distribution: {self.distro_pretty}  (family: {self.distro_family})")

    def _detect_package_manager(self) -> None:
        match self.distro_family:
            case "debian":
                if shutil.which("apt-get"):
                    self.pkg_manager = "apt"
                else:
                    log_err("apt-get not found on Debian-family system.")
            case "fedora":
                if shutil.which("dnf"):
                    self.pkg_manager = "dnf"
                else:
                    log_err("dnf not found on Fedora-family system.")
            case "arch":
                if shutil.which("pacman"):
                    self.pkg_manager = "pacman"
                else:
                    log_err("pacman not found on Arch-family system.")
                if shutil.which("paru"):
                    self.aur_helper = "paru"
                elif shutil.which("yay"):
                    self.aur_helper = "yay"
            case _:
                return

        aur_suffix = f"  (AUR: {self.aur_helper})" if self.aur_helper else ""
        log_ok(f"Package manager: {self.pkg_manager}{aur_suffix}")

    def _detect_current_de(self) -> None:
        self.current_de = (
            os.environ.get("XDG_CURRENT_DESKTOP")
            or os.environ.get("DESKTOP_SESSION")
            or os.environ.get("XDG_SESSION_DESKTOP")
            or ""
        ).lower()
        if self.current_de:
            log_ok(f"Current DE/WM: {self.current_de}")
        else:
            log_info("No DE/WM detected (tty session?).")

    def _detect_current_dm(self) -> None:
        self.current_dm = ""
        for dm in ("gdm", "gdm3", "sddm", "lightdm", "lxdm", "ly"):
            try:
                run_cmd(
                    ["systemctl", "is-active", "--quiet", dm],
                    check=True,
                    capture=True,
                    timeout=5,
                )
                self.current_dm = dm
                break
            except CommandError:
                continue

        if not self.current_dm:
            link = Path("/etc/systemd/system/display-manager.service")
            if link.is_symlink():
                target = link.resolve()
                self.current_dm = target.stem  # strip .service

        if self.current_dm:
            log_ok(f"Display manager: {self.current_dm}")
        else:
            log_info("No display manager detected.")

    def _detect_chassis(self) -> None:
        self.chassis_type = "unknown"
        chassis_file = Path("/sys/class/dmi/id/chassis_type")
        if chassis_file.exists():
            try:
                ct = int(chassis_file.read_text().strip())
            except ValueError:
                ct = -1
            if ct in (9, 10, 14):
                self.chassis_type = "laptop"
            elif ct in (3, 4, 5, 6, 7):
                self.chassis_type = "desktop"

        if self.chassis_type == "unknown":
            bat_dir = Path("/sys/class/power_supply")
            if bat_dir.exists() and any(bat_dir.glob("BAT*")):
                self.chassis_type = "laptop"
            else:
                self.chassis_type = "desktop"

        log_ok(f"Chassis type: {self.chassis_type}")

    # ── Windows detection ─────────────────────────────────────────────

    def _detect_windows_pkg_manager(self) -> None:
        if shutil.which("winget"):
            self.pkg_manager = "winget"
        elif shutil.which("choco"):
            self.pkg_manager = "choco"
        else:
            self.pkg_manager = ""
            log_info("No package manager found (install winget or chocolatey).")
            return
        log_ok(f"Package manager: {self.pkg_manager}")

    # ── Summary ───────────────────────────────────────────────────────

    def _show_summary(self) -> None:
        rows = [
            ("OS", self.distro_pretty or platform.platform()),
        ]
        if IS_LINUX:
            rows += [
                ("Distro family", self.distro_family or "unknown"),
                ("Package manager", f"{self.pkg_manager}" + (f" (AUR: {self.aur_helper})" if self.aur_helper else "")),
                ("Desktop / WM", self.current_de or "(not detected)"),
                ("Display manager", self.current_dm or "(none)"),
                ("Chassis type", self.chassis_type),
            ]
        elif IS_WINDOWS:
            rows.append(("Package manager", self.pkg_manager or "(none)"))

        if IS_LINUX:
            try:
                import subprocess as _sp
                kernel = _sp.check_output(["uname", "-r"], text=True, timeout=5).strip()
                rows.append(("Kernel", kernel))
            except Exception:
                pass

        info_table("System Detection Results", rows)
