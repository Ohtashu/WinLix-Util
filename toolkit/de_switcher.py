"""Desktop Environment / Window Manager Switcher.

Ports the DE switching logic from the Bash script: package maps per distro,
installation with verification, display manager switching, and safe removal
of the old DE with protected-package filtering.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    separator,
)
from toolkit.util import CommandError, require_sudo, run_cmd


# ── DE/WM registry ───────────────────────────────────────────────────────

@dataclass
class DEEntry:
    label: str
    debian: str = ""
    fedora: str = ""
    arch: str = ""
    dm: str = ""
    dm_pkg_debian: str = ""
    dm_pkg_fedora: str = ""
    dm_pkg_arch: str = ""


DE_REGISTRY: dict[str, DEEntry] = {
    "GNOME": DEEntry(
        label="GNOME",
        debian="gnome-session gnome-shell gnome-control-center gnome-terminal nautilus gdm3",
        fedora="@gnome-desktop",
        arch="gnome gnome-extra gdm",
        dm="gdm", dm_pkg_debian="gdm3", dm_pkg_fedora="gdm", dm_pkg_arch="gdm",
    ),
    "KDE": DEEntry(
        label="KDE Plasma",
        debian="kde-plasma-desktop sddm plasma-workspace dolphin konsole",
        fedora="@kde-desktop-environment",
        arch="plasma-meta sddm konsole dolphin",
        dm="sddm", dm_pkg_debian="sddm", dm_pkg_fedora="sddm", dm_pkg_arch="sddm",
    ),
    "XFCE": DEEntry(
        label="XFCE",
        debian="xfce4 xfce4-goodies lightdm lightdm-gtk-greeter",
        fedora="@xfce-desktop-environment",
        arch="xfce4 xfce4-goodies lightdm lightdm-gtk-greeter",
        dm="lightdm", dm_pkg_debian="lightdm", dm_pkg_fedora="lightdm", dm_pkg_arch="lightdm",
    ),
    "MATE": DEEntry(
        label="MATE",
        debian="mate-desktop-environment mate-desktop-environment-extras lightdm",
        fedora="@mate-desktop-environment",
        arch="mate mate-extra lightdm lightdm-gtk-greeter",
        dm="lightdm", dm_pkg_debian="lightdm", dm_pkg_fedora="lightdm", dm_pkg_arch="lightdm",
    ),
    "BUDGIE": DEEntry(
        label="Budgie",
        debian="budgie-desktop lightdm lightdm-gtk-greeter",
        fedora="budgie-desktop lightdm lightdm-gtk-greeter",
        arch="budgie budgie-extras lightdm lightdm-gtk-greeter",
        dm="lightdm", dm_pkg_debian="lightdm", dm_pkg_fedora="lightdm", dm_pkg_arch="lightdm",
    ),
    "HYPRLAND": DEEntry(
        label="Hyprland",
        debian="hyprland",
        fedora="hyprland",
        arch="hyprland",
    ),
    "SWAY": DEEntry(
        label="Sway",
        debian="sway swaylock swayidle swaybg foot",
        fedora="sway swaylock swayidle swaybg foot",
        arch="sway swaylock swayidle swaybg foot",
    ),
}

DE_KEYS = list(DE_REGISTRY.keys())

PROTECTED_PKGS: frozenset[str] = frozenset(
    s.lower()
    for s in [
        "networkmanager", "network-manager",
        "pipewire", "pipewire-pulse", "wireplumber",
        "pulseaudio", "pulseaudio-utils",
        "systemd", "dbus", "xorg", "xorg-server", "xorg-xinit", "xserver-xorg",
        "mesa", "mesa-utils", "linux", "linux-firmware", "linux-headers",
        "bash", "sudo", "coreutils", "glibc", "grub", "efibootmgr", "util-linux",
    ]
)


def _de_key_from_name(name: str) -> str:
    """Map a DE name (e.g. from $XDG_CURRENT_DESKTOP) to a registry key."""
    n = name.lower()
    for pattern, key in [
        ("gnome", "GNOME"), ("kde", "KDE"), ("plasma", "KDE"),
        ("xfce", "XFCE"), ("mate", "MATE"), ("budgie", "BUDGIE"),
        ("hyprland", "HYPRLAND"), ("sway", "SWAY"),
    ]:
        if pattern in n:
            return key
    return ""


# ── DE Switcher ───────────────────────────────────────────────────────────

class DESwitcher:
    """Interactive DE/WM switching wizard."""

    def __init__(self, system: SystemDetect, pkg: PackageManager) -> None:
        self.system = system
        self.pkg = pkg

    def run(self) -> None:
        banner("Module 1 — Desktop Environment / WM Switcher")

        console.print(f"  [bold]Current DE/WM :[/bold] {self.system.current_de or '(not detected)'}")
        console.print(f"  [bold]Display Mgr   :[/bold] {self.system.current_dm or '(none)'}")
        console.print(f"  [bold]Distro        :[/bold] {self.system.distro_pretty} ({self.system.pkg_manager})")
        console.print()
        separator()

        # ── List available DEs ──
        console.print()
        console.print("  [bold]Select a target environment:[/bold]")
        console.print()
        for i, key in enumerate(DE_KEYS, 1):
            entry = DE_REGISTRY[key]
            pkgs = self._get_pkgs(entry)
            if not pkgs:
                console.print(f"    [dim]{i}) {entry.label}  (no packages mapped for {self.system.distro_family})[/dim]")
            else:
                console.print(f"    [cyan]{i})[/cyan] {entry.label}")
        console.print()
        console.print("    [dim]0)[/dim] Back to main menu")
        console.print()

        from rich.prompt import Prompt
        choice = Prompt.ask("  Enter choice", default="0").strip()
        if choice == "0":
            return

        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(DE_KEYS)):
                raise ValueError
        except ValueError:
            console.print("  Invalid choice.")
            press_enter()
            return

        sel_key = DE_KEYS[idx]
        sel_entry = DE_REGISTRY[sel_key]
        sel_pkgs = self._get_pkgs(sel_entry)

        if not sel_pkgs:
            log_err(f"No packages mapped for {sel_entry.label} on {self.system.distro_family}.")
            press_enter()
            return

        # ── Confirm install ──
        section(f"Installing {sel_entry.label}")
        console.print(f"  Packages: {' '.join(sel_pkgs)}")
        console.print()
        if not confirm("Proceed with installation?"):
            log_info("Cancelled by user.")
            press_enter()
            return

        try:
            require_sudo()
        except Exception:
            press_enter()
            return

        # ── Install ──
        if not self.pkg.install(*sel_pkgs):
            log_err("Installation failed. No changes were made to your current DE.")
            press_enter()
            return

        # ── Verify every package ──
        log("Verifying installation…")
        failed = False
        for p in sel_pkgs:
            if p.startswith("@"):
                continue  # dnf group specifier
            if self.pkg.is_installed(p):
                log_ok(f"{p} installed")
            else:
                if self.system.distro_family == "arch":
                    # Could be a pacman group
                    try:
                        result = run_cmd(["pacman", "-Sg", p], check=False)
                        if result.returncode == 0:
                            log_ok(f"{p} (group)")
                            continue
                    except Exception:
                        pass
                log_err(f"{p} NOT installed")
                failed = True

        if failed:
            log_err("Verification FAILED — your current DE is still intact.")
            log_warn("Attempting to roll back partial install…")
            self.pkg.remove(*sel_pkgs)
            press_enter()
            return

        log_ok("All packages verified.")

        # ── Display manager switch ──
        self._handle_dm(sel_key, sel_entry)

        # ── Offer to remove old DE ──
        self._offer_remove_old(sel_key, sel_entry)

        console.print()
        log_ok(f"DE/WM switch to {sel_entry.label} complete. Please reboot.")
        press_enter()

    # ── Helpers ───────────────────────────────────────────────────────

    def _get_pkgs(self, entry: DEEntry) -> list[str]:
        raw = getattr(entry, self.system.distro_family, "")
        return raw.split() if raw else []

    def _get_dm_pkg(self, entry: DEEntry) -> str:
        return getattr(entry, f"dm_pkg_{self.system.distro_family}", "")

    def _handle_dm(self, sel_key: str, sel_entry: DEEntry) -> None:
        new_dm = sel_entry.dm
        if not new_dm:
            log_info(f"{sel_entry.label} is a tiling WM — no display manager required.")
            log_info(f"Launch it from a tty with:  exec {sel_entry.label.lower()}")
            return
        if self.system.current_dm == new_dm:
            log_ok(f"Recommended DM ({new_dm}) is already active.")
            return

        console.print()
        console.print(f"  {sel_entry.label} works best with the '{new_dm}' display manager.")
        if self.system.current_dm:
            console.print(f"  Your current DM is '{self.system.current_dm}'.")
        console.print()

        if not confirm(f"Switch display manager to {new_dm}?"):
            return

        dm_pkg = self._get_dm_pkg(sel_entry)
        if dm_pkg:
            self.pkg.install(dm_pkg)

        if self.system.current_dm:
            run_cmd(["systemctl", "disable", self.system.current_dm], sudo=True, check=False)

        try:
            run_cmd(["systemctl", "enable", new_dm], sudo=True)
            log_ok(f"Display manager set to {new_dm} (active after reboot).")
        except CommandError:
            log_warn(f"Could not enable {new_dm} — configure it manually.")

    def _offer_remove_old(self, sel_key: str, sel_entry: DEEntry) -> None:
        old_key = _de_key_from_name(self.system.current_de)
        if not old_key or old_key == sel_key:
            return

        old_entry = DE_REGISTRY.get(old_key)
        if not old_entry:
            return

        console.print()
        if not confirm(f"Remove old DE ({old_entry.label})?"):
            return

        old_pkgs = self._get_pkgs(old_entry)
        safe_pkgs = [p for p in old_pkgs if p.lower() not in PROTECTED_PKGS]

        if not safe_pkgs:
            log_info(f"No safely removable packages identified for {old_entry.label}.")
            return

        console.print(f"  Will remove: {' '.join(safe_pkgs)}")
        if not confirm("Confirm removal?"):
            return

        self.pkg.remove(*safe_pkgs)

        old_dm = old_entry.dm
        new_dm = sel_entry.dm
        if old_dm and old_dm != new_dm:
            run_cmd(["systemctl", "disable", old_dm], sudo=True, check=False)

        log_ok(f"Old DE ({old_entry.label}) removed.")
