"""Hardware Optimization module.

Routes to laptop-specific (TLP, auto-cpufreq) or desktop-specific
(GameMode, CPU governor) optimizations based on chassis detection.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from toolkit.detection import SystemDetect
from toolkit.packages import PackageManager
from toolkit.ui import (
    banner,
    confirm,
    console,
    log_info,
    log_ok,
    log_warn,
    press_enter,
    section,
)
from toolkit.util import CommandError, require_sudo, run_cmd


class HardwareOptimizer:
    """Laptop vs. desktop hardware tuning wizard."""

    def __init__(self, system: SystemDetect, pkg: PackageManager) -> None:
        self.system = system
        self.pkg = pkg

    def run(self) -> None:
        banner("Module 3 — Hardware Optimization")
        console.print(f"  [bold]Detected chassis:[/bold] {self.system.chassis_type}")
        console.print()

        if self.system.chassis_type == "laptop":
            self._laptop_optimizations()
        else:
            self._desktop_optimizations()

        # Common: irqbalance
        console.print()
        try:
            run_cmd(["systemctl", "is-active", "--quiet", "irqbalance"], check=True, timeout=5)
            log_ok("irqbalance is running (recommended for multi-core).")
        except CommandError:
            if confirm("Enable irqbalance for better IRQ distribution?"):
                self.pkg.install("irqbalance")
                run_cmd(["systemctl", "enable", "--now", "irqbalance"], sudo=True, check=False)
                log_ok("irqbalance enabled.")

        press_enter()

    # ── Laptop ────────────────────────────────────────────────────────

    def _laptop_optimizations(self) -> None:
        section("Laptop Optimizations")

        # TLP
        if self.pkg.is_installed("tlp"):
            log_ok("TLP is already installed.")
            try:
                run_cmd(["systemctl", "is-active", "--quiet", "tlp"], check=True, timeout=5)
                log_ok("TLP service is running.")
            except CommandError:
                if confirm("Enable and start TLP?"):
                    run_cmd(["systemctl", "enable", "--now", "tlp"], sudo=True)
                    log_ok("TLP enabled.")
        else:
            console.print("  TLP — Advanced power management for Linux laptops.")
            if confirm("Install TLP?"):
                self.pkg.install("tlp", "tlp-rdw")
                run_cmd(["systemctl", "enable", "--now", "tlp"], sudo=True, check=False)
                run_cmd(
                    ["systemctl", "mask", "systemd-rfkill.service", "systemd-rfkill.socket"],
                    sudo=True, check=False,
                )
                log_ok("TLP installed and enabled.")

        console.print()

        # auto-cpufreq
        if shutil.which("auto-cpufreq"):
            log_ok("auto-cpufreq is already installed.")
        else:
            console.print("  auto-cpufreq — Automatic CPU speed & power optimizer.")
            console.print("    (Note: do NOT run both TLP and auto-cpufreq together.)")
            if confirm("Install auto-cpufreq?"):
                self.pkg.install("auto-cpufreq")
                if shutil.which("auto-cpufreq"):
                    run_cmd(["auto-cpufreq", "--install"], sudo=True, check=False)
                    log_ok("auto-cpufreq installed.")
                else:
                    log_warn("auto-cpufreq not available in repos. Install from GitHub:")
                    console.print("    https://github.com/AdnanHodzic/auto-cpufreq")

        console.print()

        # Battery threshold (ThinkPads)
        threshold_file = Path("/sys/class/power_supply/BAT0/charge_control_end_threshold")
        if threshold_file.exists():
            try:
                val = threshold_file.read_text().strip()
                log_info(f"Battery charge threshold is currently set to: {val}%")
                console.print("    (ThinkPad-style battery health feature detected.)")
            except PermissionError:
                pass

    # ── Desktop ───────────────────────────────────────────────────────

    def _desktop_optimizations(self) -> None:
        section("Desktop / Performance Optimizations")

        # CPU governor
        console.print("  Current CPU governor(s):")
        cpu_dir = Path("/sys/devices/system/cpu/cpu0/cpufreq")
        if cpu_dir.exists():
            governors: set[str] = set()
            for gov_file in Path("/sys/devices/system/cpu").glob("cpu*/cpufreq/scaling_governor"):
                try:
                    governors.add(gov_file.read_text().strip())
                except PermissionError:
                    pass
            console.print(f"    {', '.join(sorted(governors)) if governors else '(unknown)'}")
        else:
            console.print("    (cpufreq not available)")
        console.print()

        # GameMode
        if shutil.which("gamemoded") or self.pkg.is_installed("gamemode"):
            log_ok("GameMode is already installed.")
        else:
            console.print("  GameMode — Optimises Linux system performance on demand.")
            if confirm("Install GameMode?"):
                pkgs = ["gamemode"]
                if self.system.distro_family == "arch":
                    pkgs.append("lib32-gamemode")
                self.pkg.install(*pkgs)
                log_ok("GameMode installed.  Use 'gamemoderun <game>' to activate.")

        console.print()

        # Performance governor hint
        console.print("  To set the performance CPU governor temporarily:")
        console.print("    echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor")
        console.print()
        console.print("  For persistent governor changes, consider installing cpupower:")
        match self.system.distro_family:
            case "debian":
                console.print("    sudo apt install linux-tools-common")
            case "fedora":
                console.print("    sudo dnf install kernel-tools")
            case "arch":
                console.print("    sudo pacman -S cpupower")
