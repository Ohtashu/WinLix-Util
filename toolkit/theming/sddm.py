"""SDDM theme manager with self-healing restore capability.

Manages SDDM login-screen themes:
- Apply installed SDDM themes
- Install community SDDM themes
- Set SDDM wallpaper
- macOS-style SDDM theme setup
- Self-healing: detect and restore broken SDDM configurations
"""

from __future__ import annotations

import configparser
import re
import shutil
import tempfile
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
from toolkit.util import CommandError, gh_clone, require_sudo, run_cmd

SDDM_THEMES_DIR = Path("/usr/share/sddm/themes")
SDDM_CONF = Path("/etc/sddm.conf")
SDDM_CONF_D = Path("/etc/sddm.conf.d")

COMMUNITY_SDDM_THEMES = [
    {"name": "Sugar Dark",    "repo": "https://github.com/MarianArlt/sddm-sugar-dark.git",   "folder": "sugar-dark"},
    {"name": "Sugar Candy",   "repo": "https://github.com/Kanegie/sddm-sugar-candy.git",     "folder": "sugar-candy"},
    {"name": "WhiteSur",      "repo": "https://github.com/vinceliuice/WhiteSur-kde.git",     "folder": "WhiteSur"},
    {"name": "Corners",       "repo": "https://github.com/aczw/sddm-theme-corners.git",     "folder": "corners"},
    {"name": "Aerial",        "repo": "https://github.com/3ximus/aerial-sddm-theme.git",    "folder": "aerial"},
]


class SDDMManager:
    """SDDM theme manager and self-healing restore tool."""

    def __init__(self, system: SystemDetect, pkg: PackageManager) -> None:
        self.system = system
        self.pkg = pkg

    # ── Main menu ─────────────────────────────────────────────────────

    def run(self) -> None:
        section("SDDM Theme Manager")
        console.print("    [cyan]1)[/cyan] Apply an installed SDDM theme")
        console.print("    [cyan]2)[/cyan] Install a community SDDM theme")
        console.print("    [cyan]3)[/cyan] Set SDDM background wallpaper")
        console.print()
        console.print("    [dim]0)[/dim] Cancel")
        console.print()

        from rich.prompt import Prompt
        action = Prompt.ask("  Enter choice", default="0").strip()
        match action:
            case "1": self._apply_installed()
            case "2": self._install_community()
            case "3": self._set_wallpaper()

    # ── Apply installed theme ─────────────────────────────────────────

    def _apply_installed(self) -> None:
        themes = self._list_installed()
        if not themes:
            log_warn("No SDDM themes found. Install one first.")
            return

        console.print()
        console.print("  Installed SDDM Themes:")
        console.print()
        for i, t in enumerate(themes, 1):
            console.print(f"    {i}) {t}")
        console.print(f"\n    0) Cancel\n")

        from rich.prompt import Prompt
        choice = Prompt.ask("  Select theme", default="0").strip()
        if choice == "0":
            return
        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(themes)):
                raise ValueError
        except ValueError:
            console.print("  Invalid choice.")
            return

        selected = themes[idx]
        self._write_sddm_theme(selected)

    def _list_installed(self) -> list[str]:
        """Return names of valid SDDM themes (dirs containing metadata.desktop or theme.conf)."""
        themes: list[str] = []
        if not SDDM_THEMES_DIR.is_dir():
            return themes
        for item in sorted(SDDM_THEMES_DIR.iterdir()):
            if not item.is_dir():
                continue
            if (item / "metadata.desktop").exists() or (item / "theme.conf").exists():
                themes.append(item.name)
        return themes

    def _write_sddm_theme(self, theme_name: str) -> None:
        try:
            require_sudo()
        except Exception:
            return

        run_cmd(["mkdir", "-p", str(SDDM_CONF_D)], sudo=True, check=False)

        theme_conf = SDDM_CONF_D / "theme.conf"
        content = f"[Theme]\nCurrent={theme_name}\n"
        run_cmd(["tee", str(theme_conf)], sudo=True, input_text=content)
        log_ok(f"SDDM theme set to '{theme_name}' in {theme_conf}.")

    # ── Install community theme ───────────────────────────────────────

    def _install_community(self) -> None:
        section("Install Community SDDM Themes")
        for i, t in enumerate(COMMUNITY_SDDM_THEMES, 1):
            console.print(f"    {i}) {t['name']}")
        console.print(f"\n    0) Cancel\n")

        from rich.prompt import Prompt
        pick = Prompt.ask("  Select theme", default="0").strip()
        if pick == "0":
            return
        try:
            idx = int(pick) - 1
            if not (0 <= idx < len(COMMUNITY_SDDM_THEMES)):
                raise ValueError
        except ValueError:
            console.print("  Invalid choice.")
            return

        theme = COMMUNITY_SDDM_THEMES[idx]
        log(f"Installing SDDM theme: {theme['name']}")

        try:
            require_sudo()
        except Exception:
            return

        if not shutil.which("git") and not shutil.which("gh"):
            log_err("git or gh CLI is required.")
            return

        dest = SDDM_THEMES_DIR / theme["folder"]
        if dest.exists():
            log_info(f"{dest} already exists.")
            if not confirm("Overwrite it?"):
                return
            run_cmd(["rm", "-rf", str(dest)], sudo=True)

        with tempfile.TemporaryDirectory(prefix="sddm_") as tmpdir:
            if not gh_clone(theme["repo"], tmpdir):
                log_err("Failed to clone repository.")
                return

            # Some repos put the theme in a subfolder
            src = Path(tmpdir) / theme["folder"]
            if not src.is_dir():
                # Might have an install.sh for SDDM
                install_sh = Path(tmpdir) / "sddm" / "install.sh"
                if install_sh.exists():
                    install_sh.chmod(0o755)
                    run_cmd(["bash", str(install_sh)], sudo=True, check=False)
                    log_ok(f"SDDM theme '{theme['name']}' installed via script.")
                else:
                    src = Path(tmpdir)

            if src.is_dir():
                run_cmd(["cp", "-r", str(src), str(dest)], sudo=True)
                log_ok(f"Theme installed to {dest}.")

        if confirm(f"Apply '{theme['name']}' as the active SDDM theme?"):
            self._write_sddm_theme(theme["folder"])

    # ── Set SDDM wallpaper ────────────────────────────────────────────

    def _set_wallpaper(self) -> None:
        section("Set SDDM Background Wallpaper")
        themes = self._list_installed()
        current = self._get_current_theme()

        if current and current in themes:
            target_theme = current
            log_info(f"Current SDDM theme: {current}")
        else:
            if not themes:
                log_warn("No SDDM themes found.")
                return
            console.print("  Select which SDDM theme to modify:")
            for i, t in enumerate(themes, 1):
                console.print(f"    {i}) {t}")
            console.print(f"\n    0) Cancel\n")
            from rich.prompt import Prompt
            pick = Prompt.ask("  Select theme", default="0").strip()
            if pick == "0":
                return
            try:
                idx = int(pick) - 1
                if not (0 <= idx < len(themes)):
                    raise ValueError
            except ValueError:
                console.print("  Invalid choice.")
                return
            target_theme = themes[idx]

        console.print()
        wallpaper_path = prompt("Path to wallpaper image")
        if not wallpaper_path:
            return
        wp = Path(wallpaper_path).expanduser()
        if not wp.is_file():
            log_err(f"File not found: {wp}")
            return

        theme_dir = SDDM_THEMES_DIR / target_theme
        theme_conf = theme_dir / "theme.conf"
        if not theme_conf.exists():
            log_warn(f"theme.conf not found in {theme_dir}.")
            return

        try:
            require_sudo()
        except Exception:
            return

        # Copy wallpaper into theme dir
        dest_name = f"background{wp.suffix}"
        dest = theme_dir / dest_name
        run_cmd(["cp", str(wp), str(dest)], sudo=True)

        # Update theme.conf
        content = theme_conf.read_text()
        new_content = re.sub(
            r"^Background=.*$",
            f"Background={dest_name}",
            content,
            flags=re.MULTILINE,
        )
        if "Background=" not in new_content:
            # Add it under [General] or at top
            if "[General]" in new_content:
                new_content = new_content.replace("[General]", f"[General]\nBackground={dest_name}", 1)
            else:
                new_content = f"[General]\nBackground={dest_name}\n{new_content}"

        run_cmd(["tee", str(theme_conf)], sudo=True, input_text=new_content)
        log_ok(f"SDDM wallpaper set to {dest_name} in theme '{target_theme}'.")

    # ── macOS SDDM theme ─────────────────────────────────────────────

    def macos_sddm(self) -> None:
        banner("macOS-Style SDDM Login Screen")
        log_info("Installing WhiteSur SDDM theme…")

        try:
            require_sudo()
        except Exception:
            return

        if not shutil.which("git") and not shutil.which("gh"):
            log_err("git or gh CLI is required.")
            return

        with tempfile.TemporaryDirectory(prefix="sddm_macos_") as tmpdir:
            if not gh_clone("https://github.com/vinceliuice/WhiteSur-kde.git", tmpdir):
                log_err("Failed to clone WhiteSur-kde repository.")
                return

            sddm_src = Path(tmpdir) / "sddm"
            if sddm_src.is_dir():
                install_sh = sddm_src / "install.sh"
                if install_sh.exists():
                    install_sh.chmod(0o755)
                    run_cmd(["bash", str(install_sh)], sudo=True, check=False)
                    log_ok("WhiteSur SDDM theme installed via script.")
                else:
                    for item in sddm_src.iterdir():
                        if item.is_dir():
                            dest = SDDM_THEMES_DIR / item.name
                            run_cmd(["cp", "-r", str(item), str(dest)], sudo=True, check=False)
                            log_ok(f"SDDM theme copied to {dest}.")
            else:
                log_warn("SDDM subfolder not found in WhiteSur-kde repo.")
                return

        # Try to find and apply the theme
        for candidate in ("WhiteSur", "whitesur"):
            if (SDDM_THEMES_DIR / candidate).is_dir():
                self._write_sddm_theme(candidate)
                break

    # ── Self-healing: restore SDDM default ────────────────────────────

    def restore_sddm_default(self) -> None:
        """Detect and fix broken SDDM configurations, restore defaults."""
        banner("SDDM Self-Healing / Restore Default")

        try:
            require_sudo()
        except Exception:
            return

        problems: list[str] = []
        fixes: list[str] = []

        # Step 1: Scan /etc/sddm.conf for broken [Theme] blocks
        if SDDM_CONF.exists():
            log("Scanning /etc/sddm.conf…")
            content = SDDM_CONF.read_text()
            theme_match = re.search(r"^\[Theme\]\s*\nCurrent=(.+)$", content, re.MULTILINE)
            if theme_match:
                theme_name = theme_match.group(1).strip()
                if theme_name and not (SDDM_THEMES_DIR / theme_name).is_dir():
                    problems.append(f"/etc/sddm.conf: Theme '{theme_name}' not found in {SDDM_THEMES_DIR}")
                elif not theme_name:
                    problems.append("/etc/sddm.conf: Empty theme value in [Theme] section")

        # Step 2: Scan /etc/sddm.conf.d/ for overrides
        if SDDM_CONF_D.is_dir():
            log(f"Scanning {SDDM_CONF_D}…")
            for conf_file in sorted(SDDM_CONF_D.glob("*.conf")):
                try:
                    content = conf_file.read_text()
                except PermissionError:
                    problems.append(f"{conf_file}: Permission denied reading file")
                    continue
                theme_match = re.search(r"^\[Theme\]\s*\nCurrent=(.+)$", content, re.MULTILINE)
                if theme_match:
                    theme_name = theme_match.group(1).strip()
                    if theme_name and not (SDDM_THEMES_DIR / theme_name).is_dir():
                        problems.append(f"{conf_file}: Theme '{theme_name}' not found in {SDDM_THEMES_DIR}")
                    elif not theme_name:
                        problems.append(f"{conf_file}: Empty theme value in [Theme] section")

        # Step 3: Check if SDDM service is active
        sddm_running = False
        if shutil.which("systemctl"):
            try:
                r = run_cmd(["systemctl", "is-active", "sddm"], check=False)
                sddm_running = (r.stdout or "").strip() == "active"
            except CommandError:
                pass

        # Report findings
        console.print()
        if not problems:
            console.print("  [green]No broken SDDM theme configurations detected.[/green]")
            console.print()
            if not confirm("Reset to default SDDM theme anyway?"):
                return
        else:
            console.print("  [bold yellow]Problems detected:[/bold yellow]")
            for p in problems:
                console.print(f"    ⚠  {p}")
            console.print()
            if not confirm("Fix these issues and reset SDDM to defaults?"):
                return

        # Step 4: Backup broken configs
        from datetime import datetime
        timestamp = f"{datetime.now():%Y%m%d_%H%M%S}"
        bak_dir = Path(f"/etc/sddm_backup_{timestamp}")

        if SDDM_CONF.exists() or SDDM_CONF_D.is_dir():
            run_cmd(["mkdir", "-p", str(bak_dir)], sudo=True)
            if SDDM_CONF.exists():
                run_cmd(["cp", str(SDDM_CONF), str(bak_dir / "sddm.conf")], sudo=True)
                fixes.append(f"Backed up {SDDM_CONF}")
            if SDDM_CONF_D.is_dir():
                run_cmd(["cp", "-r", str(SDDM_CONF_D), str(bak_dir / "sddm.conf.d")], sudo=True)
                fixes.append(f"Backed up {SDDM_CONF_D}")

        # Step 5: Remove [Theme] blocks from sddm.conf
        if SDDM_CONF.exists():
            content = SDDM_CONF.read_text()
            cleaned = re.sub(
                r"\[Theme\]\s*\n(?:(?!\[)[^\n]*\n)*",
                "",
                content,
            ).strip()
            if cleaned:
                run_cmd(["tee", str(SDDM_CONF)], sudo=True, input_text=cleaned + "\n")
            else:
                run_cmd(["rm", str(SDDM_CONF)], sudo=True)
            fixes.append(f"Cleaned [Theme] block from {SDDM_CONF}")

        # Step 6: Remove theme overrides from sddm.conf.d
        if SDDM_CONF_D.is_dir():
            for conf_file in SDDM_CONF_D.glob("*.conf"):
                content = conf_file.read_text()
                if "[Theme]" in content:
                    cleaned = re.sub(
                        r"\[Theme\]\s*\n(?:(?!\[)[^\n]*\n)*",
                        "",
                        content,
                    ).strip()
                    if cleaned:
                        run_cmd(["tee", str(conf_file)], sudo=True, input_text=cleaned + "\n")
                    else:
                        run_cmd(["rm", str(conf_file)], sudo=True)
                    fixes.append(f"Cleaned [Theme] block from {conf_file}")

        # Step 7: Restart SDDM if running
        if sddm_running:
            log("Restarting SDDM…")
            try:
                run_cmd(["systemctl", "restart", "sddm"], sudo=True, timeout=15)
                fixes.append("SDDM service restarted")
                log_ok("SDDM restarted successfully.")
            except CommandError as e:
                log_err(f"Failed to restart SDDM: {e.stderr}")
                console.print()
                console.print("  [bold yellow]SDDM failed to restart. Recovery options:[/bold yellow]")
                console.print("    1) Switch to a TTY: Ctrl+Alt+F2")
                console.print("    2) Log in as your user")
                console.print(f"    3) Restore backup: sudo cp {bak_dir}/sddm.conf /etc/sddm.conf")
                console.print("    4) Restart SDDM: sudo systemctl restart sddm")
                console.print("    5) Or reboot: sudo reboot")
        else:
            log_info("SDDM is not currently running — changes take effect on next DM start.")

        # Summary
        console.print()
        if fixes:
            console.print("  [bold green]Fixes applied:[/bold green]")
            for f in fixes:
                console.print(f"    ✔ {f}")
            log_ok(f"SDDM restored to defaults. Backups saved in {bak_dir}.")
        else:
            console.print("  No changes were necessary.")

    # ── Helpers ───────────────────────────────────────────────────────

    def _get_current_theme(self) -> str:
        """Read the currently configured SDDM theme name."""
        # Check sddm.conf.d first (overrides)
        if SDDM_CONF_D.is_dir():
            for conf_file in sorted(SDDM_CONF_D.glob("*.conf"), reverse=True):
                try:
                    content = conf_file.read_text()
                except PermissionError:
                    continue
                m = re.search(r"^\[Theme\]\s*\nCurrent=(.+)$", content, re.MULTILINE)
                if m:
                    return m.group(1).strip()

        if SDDM_CONF.exists():
            try:
                content = SDDM_CONF.read_text()
            except PermissionError:
                return ""
            m = re.search(r"^\[Theme\]\s*\nCurrent=(.+)$", content, re.MULTILINE)
            if m:
                return m.group(1).strip()

        return ""
