"""Windows theming — dark mode toggle and accent colour via winreg.

All operations are guarded by platform checks so importing this module
on Linux is safe (but methods will no-op).
"""

from __future__ import annotations

import platform

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

_IS_WIN = platform.system() == "Windows"


class WindowsTheming:
    """Windows dark mode and accent colour via the Windows Registry."""

    def __init__(self, system: SystemDetect | None = None, pkg: PackageManager | None = None) -> None:
        self.system = system
        self.pkg = pkg

    # ── Dark mode toggle ──────────────────────────────────────────────

    def toggle_dark_mode(self) -> None:
        banner("Windows Dark / Light Mode Toggle")

        if not _IS_WIN:
            log_err("This feature is only available on Windows.")
            return

        import winreg  # type: ignore[import-not-found]

        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            apps_val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            sys_val, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
            winreg.CloseKey(key)
        except FileNotFoundError:
            apps_val = 1
            sys_val = 1

        current = "Light" if apps_val == 1 else "Dark"
        console.print(f"  Current mode: [bold]{current}[/bold]")
        console.print()

        new_mode = "Dark" if current == "Light" else "Light"
        if not confirm(f"Switch to {new_mode} mode?"):
            return

        new_val = 0 if new_mode == "Dark" else 1
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, new_val)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, new_val)
            winreg.CloseKey(key)
            log_ok(f"Switched to {new_mode} mode. Some apps may need a restart.")
        except PermissionError:
            log_err("Permission denied. Run as administrator or check registry access.")
        except Exception as exc:
            log_err(f"Failed to update registry: {exc}")

    # ── Accent colour ─────────────────────────────────────────────────

    def set_accent_color_interactive(self) -> None:
        banner("Windows Accent Colour")

        if not _IS_WIN:
            log_err("This feature is only available on Windows.")
            return

        import winreg  # type: ignore[import-not-found]

        console.print("  Enter a colour in hex format (e.g., #0078D4 for Windows blue).")
        console.print()
        hex_input = prompt("Hex colour (#RRGGBB)")
        if not hex_input:
            return

        hex_input = hex_input.strip().lstrip("#")
        if len(hex_input) != 6:
            log_err("Invalid hex colour. Expected 6 hex digits (e.g., 0078D4).")
            return

        try:
            r = int(hex_input[0:2], 16)
            g = int(hex_input[2:4], 16)
            b = int(hex_input[4:6], 16)
        except ValueError:
            log_err("Invalid hex characters.")
            return

        # DWM AccentColor is stored as 0xAABBGGRR (ABGR)
        accent_abgr = 0xFF000000 | (b << 16) | (g << 8) | r
        # ColorizationColor is also ABGR with alpha
        colorization = accent_abgr

        dwm_path = r"SOFTWARE\Microsoft\Windows\DWM"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, dwm_path, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "AccentColor", 0, winreg.REG_DWORD, accent_abgr & 0xFFFFFFFF)
            winreg.SetValueEx(key, "ColorizationColor", 0, winreg.REG_DWORD, colorization & 0xFFFFFFFF)
            winreg.SetValueEx(key, "ColorizationAfterglow", 0, winreg.REG_DWORD, colorization & 0xFFFFFFFF)
            winreg.CloseKey(key)
            log_ok(f"Accent colour set to #{hex_input.upper()} (RGB: {r},{g},{b}).")
            log_info("Some apps and taskbar elements may need a restart to reflect the change.")
        except PermissionError:
            log_err("Permission denied. Run as administrator.")
        except Exception as exc:
            log_err(f"Failed to update registry: {exc}")
