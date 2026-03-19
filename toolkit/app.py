"""Main application — entry point, banner, menu loop, module dispatch.

Run via:
    python -m toolkit
    linux-toolkit          (if installed via pip / pipx)
"""

from __future__ import annotations

import sys

from toolkit.detection import SystemDetect
from toolkit.packages import PackageManager
from toolkit.ui import (
    banner,
    console,
    log_err,
    log_info,
    log_ok,
    log_warn,
    menu_table,
    press_enter,
    separator,
)
from toolkit.util import IS_LINUX, IS_WINDOWS, check_not_root

_ASCII_ART = r"""
  ╦  ╦╔╗╔╦ ╦═╗ ╦   ╔╦╗╔═╗╔═╗╦  ╦╔═╦╔╦╗
  ║  ║║║║║ ║╔╩╦╝    ║ ║ ║║ ║║  ║╠╩╗║ ║
  ╩═╝╩╝╚╝╚═╝╩ ╚═    ╩ ╚═╝╚═╝╩═╝╩ ╩╩ ╩
"""


class App:
    """Top-level application controller."""

    def __init__(self) -> None:
        self.system = SystemDetect()
        self.system.detect_all()
        self.pkg = PackageManager(self.system)

    # ── Module factories (lazy) ───────────────────────────────────────

    def _de_switcher(self):
        from toolkit.de_switcher import DESwitcher
        return DESwitcher(self.system, self.pkg)

    def _maintenance(self):
        from toolkit.maintenance import SystemMaintenance
        return SystemMaintenance(self.system, self.pkg)

    def _hardware(self):
        from toolkit.hardware import HardwareOptimizer
        return HardwareOptimizer(self.system, self.pkg)

    def _dev_tools(self):
        from toolkit.dev_tools import DevTools
        return DevTools(self.system, self.pkg)

    def _theming(self):
        from toolkit.theming.base import Theming
        return Theming(self.system, self.pkg)

    def _webdev(self):
        from toolkit.webdev import WebDevSetup
        return WebDevSetup(self.system, self.pkg)

    # ── Menu ──────────────────────────────────────────────────────────

    def _build_menu(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        if IS_LINUX:
            items.append(("1", "DE / WM Switcher"))
            items.append(("2", "System Maintenance"))
            items.append(("3", "Hardware Optimization"))
        items.append(("4", "Developer Tools"))
        items.append(("5", "Theming Engine"))
        items.append(("6", "Web Development Setup"))
        items.append(("0", "Exit"))
        return items

    def main_menu(self) -> None:
        while True:
            console.clear()
            console.print(_ASCII_ART, style="bold cyan")
            banner("Linux Toolkit  v2.0", subtitle=self.system.distro_pretty or self.system.os_type)
            separator()

            items = self._build_menu()
            menu_table(items)
            console.print()

            from rich.prompt import Prompt
            choice = Prompt.ask("  Enter choice", default="0").strip()

            try:
                match choice:
                    case "1" if IS_LINUX:
                        self._de_switcher().run()
                    case "2" if IS_LINUX:
                        self._maintenance().run()
                    case "3" if IS_LINUX:
                        self._hardware().run()
                    case "4":
                        self._dev_tools().run()
                    case "5":
                        self._theming().run()
                    case "6":
                        self._webdev().run()
                    case "0":
                        console.print("\n  [bold]Goodbye![/bold]\n")
                        break
                    case _:
                        log_warn("Invalid option.")
            except KeyboardInterrupt:
                console.print("\n  [dim]Interrupted.[/dim]")
            except Exception as exc:
                log_err(f"Unhandled error: {exc}")

            press_enter()


def main() -> None:
    """CLI entry point."""
    check_not_root()
    try:
        app = App()
        app.main_menu()
    except KeyboardInterrupt:
        console.print("\n  [dim]Exiting…[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    main()
