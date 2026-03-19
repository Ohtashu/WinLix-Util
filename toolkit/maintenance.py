"""System Maintenance & Bug Check module.

Ports disk health checks (SSD TRIM, SMART), broken package fixes, and
driver/firmware checks from the Bash script.
"""

from __future__ import annotations

import glob as _glob
import shutil
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
)
from toolkit.util import CommandError, require_sudo, run_cmd


class SystemMaintenance:
    """Disk health, broken-package repair, and driver diagnostics."""

    def __init__(self, system: SystemDetect, pkg: PackageManager) -> None:
        self.system = system
        self.pkg = pkg

    def run(self) -> None:
        banner("Module 2 — System Maintenance & Bug Check")
        console.print("  [bold]Select a check to run:[/bold]")
        console.print()
        console.print("    [cyan]1)[/cyan] Disk Health (SSD TRIM, SMART)")
        console.print("    [cyan]2)[/cyan] Broken Packages")
        console.print("    [cyan]3)[/cyan] Driver & Firmware Check")
        console.print("    [cyan]4)[/cyan] Run All Checks")
        console.print()
        console.print("    [dim]0)[/dim] Back to main menu")
        console.print()

        from rich.prompt import Prompt
        choice = Prompt.ask("  Enter choice", default="0").strip()

        match choice:
            case "1":
                self._disk_health()
            case "2":
                try:
                    require_sudo()
                except Exception:
                    press_enter()
                    return
                self._fix_packages()
            case "3":
                self._driver_check()
            case "4":
                try:
                    require_sudo()
                except Exception:
                    press_enter()
                    return
                self._disk_health()
                self._fix_packages()
                self._driver_check()
            case "0":
                return
            case _:
                console.print("  Invalid choice.")

        press_enter()

    # ── Disk Health ───────────────────────────────────────────────────

    def _disk_health(self) -> None:
        section("Disk Health")

        # Detect SSD vs HDD
        for pattern in ("sd*", "nvme*", "vd*"):
            for dev in sorted(Path("/sys/block").glob(pattern)):
                name = dev.name
                rotational_file = dev / "queue" / "rotational"
                rotational = "1"
                if rotational_file.exists():
                    rotational = rotational_file.read_text().strip()
                if rotational == "0":
                    console.print(f"  [ok]{name}[/ok] — SSD / NVMe")
                else:
                    console.print(f"  [warn]{name}[/warn] — HDD (rotational)")

        # fstrim.timer
        console.print()
        try:
            run_cmd(["systemctl", "list-unit-files", "fstrim.timer"], check=True, timeout=5)
            try:
                run_cmd(["systemctl", "is-active", "--quiet", "fstrim.timer"], check=True, timeout=5)
                log_ok("fstrim.timer is already active.")
            except CommandError:
                if confirm("Enable weekly SSD TRIM via fstrim.timer?"):
                    require_sudo()
                    run_cmd(["systemctl", "enable", "--now", "fstrim.timer"], sudo=True)
                    log_ok("fstrim.timer enabled and started.")
        except CommandError:
            log_info("fstrim.timer unit not found (may not be needed for your setup).")

        # SMART check
        console.print()
        if shutil.which("smartctl"):
            log("Running SMART health check…")
            for pattern in ("/dev/sd?", "/dev/nvme?n?"):
                for blk in sorted(_glob.glob(pattern)):
                    console.print()
                    console.print(f"  [bold]{blk}[/bold]")
                    try:
                        result = run_cmd(["smartctl", "-H", blk], sudo=True, check=False)
                        if result.stdout:
                            for line in result.stdout.splitlines():
                                low = line.lower()
                                if "result" in low or "status" in low:
                                    console.print(f"    {line.strip()}")
                    except CommandError:
                        pass
        else:
            log_info("smartmontools not installed. Install it for SMART diagnostics.")
            if confirm("Install smartmontools now?"):
                self.pkg.install("smartmontools")
                log_ok("smartmontools installed.")

    # ── Broken Packages ───────────────────────────────────────────────

    def _fix_packages(self) -> None:
        section("Broken Package Check")

        match self.system.distro_family:
            case "debian":
                self._fix_debian()
            case "fedora":
                self._fix_fedora()
            case "arch":
                self._fix_arch()

    def _fix_debian(self) -> None:
        log("Running dpkg --audit …")
        result = run_cmd(["dpkg", "--audit"], sudo=True, check=False)
        audit = (result.stdout or "").strip()
        if not audit:
            log_ok("No broken packages detected (dpkg).")
        else:
            for line in audit.splitlines()[:20]:
                console.print(f"    {line}")
            if confirm("Attempt to fix with apt --fix-broken install?"):
                try:
                    run_cmd(["apt-get", "install", "--fix-broken", "-y"], sudo=True)
                    log_ok("Fix completed.")
                except CommandError:
                    log_err("Fix failed — see log file.")

        try:
            run_cmd(["apt-get", "check"], sudo=True)
            log_ok("apt-get check passed.")
        except CommandError:
            log_warn("apt-get check reported issues.")
            if confirm("Run dpkg --configure -a?"):
                run_cmd(["dpkg", "--configure", "-a"], sudo=True, check=False)

    def _fix_fedora(self) -> None:
        log("Running dnf check …")
        result = run_cmd(["dnf", "check"], sudo=True, check=False)
        issues = (result.stdout or "").strip()
        if not issues:
            log_ok("No package issues detected (dnf).")
        else:
            for line in issues.splitlines()[:20]:
                console.print(f"    {line}")
            if confirm("Run dnf distro-sync to fix?"):
                try:
                    run_cmd(["dnf", "distro-sync", "-y"], sudo=True)
                    log_ok("distro-sync completed.")
                except CommandError:
                    log_err("distro-sync failed — see log file.")

    def _fix_arch(self) -> None:
        log("Checking for orphaned packages…")
        result = run_cmd(["pacman", "-Qdtq"], check=False)
        orphans = (result.stdout or "").strip()
        if not orphans:
            log_ok("No orphaned packages found.")
        else:
            orphan_list = orphans.splitlines()
            log_warn(f"{len(orphan_list)} orphaned package(s) found:")
            for line in orphan_list[:20]:
                console.print(f"    {line}")
            if confirm("Remove all orphaned packages?"):
                try:
                    run_cmd(
                        ["pacman", "-Rns", "--noconfirm", *orphan_list],
                        sudo=True,
                    )
                    log_ok("Orphans removed.")
                except CommandError:
                    log_err("Removal failed — see log file.")

        log("Checking pacman database…")
        try:
            run_cmd(["pacman", "-Dk"], sudo=True)
            log_ok("Pacman database consistent.")
        except CommandError:
            log_warn("Pacman database reported issues — see log file.")

    # ── Driver / Firmware Check ───────────────────────────────────────

    def _driver_check(self) -> None:
        section("Driver & Firmware Check")

        if not shutil.which("lspci"):
            log_info("lspci not found. Installing pciutils…")
            self.pkg.install("pciutils")

        # GPU detection
        try:
            lspci_out = run_cmd(["lspci"], check=False).stdout or ""
        except CommandError:
            lspci_out = ""

        if "nvidia" in lspci_out.lower():
            log_warn("NVIDIA GPU detected.")
            console.print("    [warn]You may need proprietary NVIDIA drivers.[/warn]")
            match self.system.distro_family:
                case "debian":
                    console.print("    Recommendation: sudo apt install nvidia-driver")
                case "fedora":
                    console.print("    Recommendation: Enable RPM Fusion, then:")
                    console.print("      sudo dnf install akmod-nvidia xorg-x11-drv-nvidia")
                case "arch":
                    console.print("    Recommendation: sudo pacman -S nvidia nvidia-utils")
            console.print()
        else:
            log_ok("No NVIDIA GPU detected (or using nouveau).")

        if any(x in lspci_out.lower() for x in ("amd", "radeon", "amdgpu")):
            log_ok("AMD GPU detected — open-source amdgpu driver is usually included.")

        if "intel" in lspci_out.lower() and ("vga" in lspci_out.lower() or "graphics" in lspci_out.lower()):
            log_ok("Intel GPU detected — i915 driver is typically built-in.")

        # Network driver check
        console.print()
        log("Checking for network device drivers…")
        try:
            result = run_cmd(["lspci", "-k"], check=False)
            output = result.stdout or ""
            net_lines = []
            capture_next = 0
            for line in output.splitlines():
                low = line.lower()
                if "network" in low or "wireless" in low:
                    net_lines.append(line)
                    capture_next = 2
                elif capture_next > 0:
                    net_lines.append(line)
                    capture_next -= 1

            has_driver = any("kernel driver" in l.lower() for l in net_lines)
            if net_lines:
                for line in net_lines:
                    console.print(f"    {line.strip()}")
                if has_driver:
                    log_ok("Network drivers appear loaded.")
                else:
                    log_warn("No kernel driver loaded for network device — possible missing firmware.")
        except CommandError:
            pass

        # USB summary
        if shutil.which("lsusb"):
            console.print()
            log("USB device summary:")
            try:
                result = run_cmd(["lsusb"], check=False)
                if result.stdout:
                    for line in result.stdout.splitlines()[:15]:
                        console.print(f"    {line}")
            except CommandError:
                pass
