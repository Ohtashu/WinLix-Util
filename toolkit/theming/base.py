"""Theming engine router — dispatches to OS-specific theming modules."""

from __future__ import annotations

from toolkit.detection import SystemDetect
from toolkit.packages import PackageManager
from toolkit.ui import banner, console, log_info, press_enter
from toolkit.util import IS_LINUX, IS_WINDOWS


class Theming:
    """Top-level theming menu that routes to KDE, SDDM, WM, Firefox, or Windows modules."""

    def __init__(self, system: SystemDetect, pkg: PackageManager) -> None:
        self.system = system
        self.pkg = pkg

    def run(self) -> None:
        banner("Module 5 — Automated Theming Engine")

        if IS_WINDOWS:
            self._windows_menu()
        elif IS_LINUX:
            self._linux_menu()
        else:
            log_info("Theming is not supported on this platform.")
            press_enter()

    # ── Linux theming submenu ─────────────────────────────────────────

    def _linux_menu(self) -> None:
        console.print("  [bold]Select theming mode:[/bold]")
        console.print()
        console.print("    [cyan]1)[/cyan] KDE Plasma — Apply / Install Global Themes")
        console.print("    [cyan]2)[/cyan] SDDM — Login Screen Themes")
        console.print("    [cyan]3)[/cyan] WM Dotfiles — Fetch & apply community dotfiles (Hyprland/Sway/…)")
        console.print("    [cyan]4)[/cyan] Firefox — WhiteSur macOS-style browser theme")
        console.print("    [cyan]5)[/cyan] 🍎 macOS Look — One-click full macOS-style setup")
        console.print("    [cyan]6)[/cyan] 🍎 macOS SDDM Theme — WhiteSur login screen")
        console.print("    [cyan]7)[/cyan] 🔄 Restore Default KDE Layout — Undo layout changes / factory reset")
        console.print("    [cyan]8)[/cyan] 🛠  SDDM Self-Heal — Restore default SDDM if login screen is broken")
        console.print()
        console.print("    [dim]0)[/dim] Back to main menu")
        console.print()

        from rich.prompt import Prompt
        choice = Prompt.ask("  Enter choice", default="0").strip()

        match choice:
            case "1":
                from toolkit.theming.kde import KDEThemer
                KDEThemer(self.system, self.pkg).run_themes()
            case "2":
                from toolkit.theming.sddm import SDDMManager
                SDDMManager(self.system, self.pkg).run()
            case "3":
                from toolkit.theming.wm_dotfiles import WMDotfiles
                WMDotfiles(self.system, self.pkg).run()
            case "4":
                from toolkit.theming.firefox import FirefoxThemer
                FirefoxThemer(self.system, self.pkg).run()
            case "5":
                from toolkit.theming.kde import KDEThemer
                KDEThemer(self.system, self.pkg).macos_setup()
            case "6":
                from toolkit.theming.sddm import SDDMManager
                SDDMManager(self.system, self.pkg).macos_sddm()
            case "7":
                from toolkit.theming.kde import KDEThemer
                KDEThemer(self.system, self.pkg).restore_default_layout()
            case "8":
                from toolkit.theming.sddm import SDDMManager
                SDDMManager(self.system, self.pkg).restore_sddm_default()
            case "0":
                return
            case _:
                console.print("  Invalid choice.")

        press_enter()

    # ── Windows theming submenu ───────────────────────────────────────

    def _windows_menu(self) -> None:
        console.print("  [bold]Windows Theming Options:[/bold]")
        console.print()
        console.print("    [cyan]1)[/cyan] Toggle Dark Mode")
        console.print("    [cyan]2)[/cyan] Set System Accent Color")
        console.print()
        console.print("    [dim]0)[/dim] Back to main menu")
        console.print()

        from rich.prompt import Prompt
        choice = Prompt.ask("  Enter choice", default="0").strip()

        match choice:
            case "1":
                from toolkit.theming.windows import WindowsTheming
                WindowsTheming().toggle_dark_mode()
            case "2":
                from toolkit.theming.windows import WindowsTheming
                WindowsTheming().set_accent_color_interactive()
            case "0":
                return
            case _:
                console.print("  Invalid choice.")

        press_enter()
