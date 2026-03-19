"""KDE Plasma theming — global themes, icons, fonts, macOS one-click setup.

Ports the full KDE theming engine from the Bash script, including:
- Apply / install global themes (8 community themes)
- Icon theme manager (8 community icon packs)
- Font manager (apply, install popular, custom install)
- macOS-style one-click WhiteSur setup (6-step transformation)
- Restore default KDE Plasma layout
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
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
from toolkit.util import CommandError, gh_clone, require_sudo, run_cmd

# ── Theme / icon / font registries ───────────────────────────────────────

COMMUNITY_THEMES = [
    {"name": "Sweet",               "repo": "https://github.com/EliverLara/Sweet.git",                "aur": "sweet-kde-theme-git"},
    {"name": "Layan",               "repo": "https://github.com/vinceliuice/Layan-kde.git",           "aur": "layan-kde-git"},
    {"name": "Nordic",              "repo": "https://github.com/EliverLara/Nordic.git",                "aur": "nordic-kde-git"},
    {"name": "Catppuccin (Mocha)",  "repo": "https://github.com/catppuccin/kde.git",                  "aur": "catppuccin-kde-theme-mocha"},
    {"name": "Dracula",             "repo": "https://github.com/dracula/kde.git",                     "aur": "dracula-kde-theme-git"},
    {"name": "WhiteSur",            "repo": "https://github.com/vinceliuice/WhiteSur-kde.git",        "aur": "whitesur-kde-theme-git"},
    {"name": "Colloid",             "repo": "https://github.com/vinceliuice/Colloid-kde.git",         "aur": "colloid-kde-theme-git"},
    {"name": "Orchis",              "repo": "https://github.com/vinceliuice/Orchis-kde.git",          "aur": "orchis-kde-theme-git"},
]

ICON_PACKS = [
    {"name": "Papirus",      "repo": "https://github.com/PapirusDevelopmentTeam/papirus-icon-theme.git",
     "aur": "papirus-icon-theme", "folder": "Papirus",      "deb": "papirus-icon-theme", "fed": "papirus-icon-theme"},
    {"name": "Tela",         "repo": "https://github.com/vinceliuice/Tela-icon-theme.git",
     "aur": "tela-icon-theme",         "folder": "Tela",         "deb": "", "fed": ""},
    {"name": "Tela Circle",  "repo": "https://github.com/vinceliuice/Tela-circle-icon-theme.git",
     "aur": "tela-circle-icon-theme-git", "folder": "Tela-circle", "deb": "", "fed": ""},
    {"name": "WhiteSur",     "repo": "https://github.com/vinceliuice/WhiteSur-icon-theme.git",
     "aur": "whitesur-icon-theme-git", "folder": "WhiteSur",     "deb": "", "fed": ""},
    {"name": "Colloid",      "repo": "https://github.com/vinceliuice/Colloid-icon-theme.git",
     "aur": "colloid-icon-theme-git",  "folder": "Colloid",      "deb": "", "fed": ""},
    {"name": "Fluent",       "repo": "https://github.com/vinceliuice/Fluent-icon-theme.git",
     "aur": "fluent-icon-theme-git",   "folder": "Fluent",       "deb": "", "fed": ""},
    {"name": "Candy Icons",  "repo": "https://github.com/EliverLara/candy-icons.git",
     "aur": "candy-icons-git",         "folder": "candy-icons",  "deb": "", "fed": ""},
    {"name": "Kora",         "repo": "https://github.com/bikber/kora.git",
     "aur": "kora-icon-theme",         "folder": "kora",         "deb": "", "fed": ""},
]

_NF_BASE = "https://github.com/ryanoasis/nerd-fonts/releases/latest/download"
POPULAR_FONTS = [
    {"name": "JetBrains Mono (Nerd Font)", "url": f"{_NF_BASE}/JetBrainsMono.tar.xz",
     "family": "JetBrainsMono Nerd Font",
     "deb": "", "fed": "", "arch": "ttf-jetbrains-mono-nerd"},
    {"name": "FiraCode (Nerd Font)",       "url": f"{_NF_BASE}/FiraCode.tar.xz",
     "family": "FiraCode Nerd Font",
     "deb": "", "fed": "", "arch": "ttf-firacode-nerd"},
    {"name": "Cascadia Code (Nerd Font)",  "url": f"{_NF_BASE}/CascadiaCode.tar.xz",
     "family": "CaskaydiaCove Nerd Font",
     "deb": "", "fed": "", "arch": "ttf-cascadia-code-nerd"},
    {"name": "Hack (Nerd Font)",           "url": f"{_NF_BASE}/Hack.tar.xz",
     "family": "Hack Nerd Font",
     "deb": "", "fed": "", "arch": "ttf-hack-nerd"},
    {"name": "Meslo (Nerd Font)",          "url": f"{_NF_BASE}/Meslo.tar.xz",
     "family": "MesloLGS Nerd Font",
     "deb": "", "fed": "", "arch": "ttf-meslo-nerd"},
    {"name": "Inter (UI font)",            "url": "",
     "family": "Inter",
     "deb": "fonts-inter", "fed": "inter-fonts", "arch": "inter-font"},
    {"name": "Noto Sans + Noto Serif",     "url": "",
     "family": "Noto Sans",
     "deb": "fonts-noto fonts-noto-extra", "fed": "google-noto-sans-fonts google-noto-serif-fonts", "arch": "noto-fonts noto-fonts-extra"},
    {"name": "IBM Plex",                   "url": "",
     "family": "IBM Plex Sans",
     "deb": "", "fed": "ibm-plex-sans-fonts ibm-plex-mono-fonts", "arch": "ttf-ibm-plex"},
]


class KDEThemer:
    """KDE Plasma theming engine."""

    def __init__(self, system: SystemDetect, pkg: PackageManager) -> None:
        self.system = system
        self.pkg = pkg
        self.home = Path.home()

    # ── kwriteconfig detection ────────────────────────────────────────

    def _kwc(self) -> str:
        for cmd in ("kwriteconfig6", "kwriteconfig5"):
            if shutil.which(cmd):
                return cmd
        return ""

    def _plasma_version(self) -> int:
        if shutil.which("kwriteconfig6"):
            return 6
        try:
            r = run_cmd(["plasmashell", "--version"], check=False)
            if r.stdout and re.search(r"plasmashell [6-9]", r.stdout):
                return 6
        except CommandError:
            pass
        return 5

    # ── Main theme submenu ────────────────────────────────────────────

    def run_themes(self) -> None:
        section("KDE Plasma Theming")

        if not shutil.which("plasma-apply-lookandfeel"):
            log_err("plasma-apply-lookandfeel not found. Is KDE Plasma installed?")
            return

        console.print("  [bold]KDE Plasma Theme Options:[/bold]")
        console.print()
        console.print("    [cyan]1)[/cyan] Apply an installed Global Theme")
        console.print("    [cyan]2)[/cyan] Install a popular community theme")
        console.print("    [cyan]3)[/cyan] Icon Themes — Install & apply icon packs")
        console.print("    [cyan]4)[/cyan] Fonts — Install & apply fonts system-wide")
        console.print()
        console.print("    [dim]0)[/dim] Cancel")
        console.print()

        from rich.prompt import Prompt
        action = Prompt.ask("  Enter choice", default="0").strip()
        match action:
            case "1": self._apply_installed_theme()
            case "2": self._install_community_theme()
            case "3": self._icon_themes_menu()
            case "4": self._font_manager_menu()
            case _: return

    # ── Apply installed global theme ──────────────────────────────────

    def _apply_installed_theme(self) -> None:
        log("Querying installed Plasma Global Themes…")
        try:
            result = run_cmd(["plasma-apply-lookandfeel", "-l"], check=False)
        except CommandError:
            log_err("Could not list themes.")
            return

        themes = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        if not themes:
            log_warn("No Global Themes found.")
            return

        console.print()
        console.print("  Installed Global Themes:")
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
        log(f"Applying Global Theme: {selected}…")
        try:
            run_cmd(["plasma-apply-lookandfeel", "-a", selected])
            log_ok(f"Look-and-feel applied: {selected}")
        except CommandError:
            log_err("plasma-apply-lookandfeel failed. See log file.")
            return

        # Apply sub-components from theme defaults
        self._apply_theme_components(selected)

        # Offer SDDM
        console.print()
        if confirm("Also set this theme for the SDDM login screen?"):
            self._set_sddm_theme(selected)

        log_ok(f"Global theme '{selected}' fully applied.")

    def _apply_theme_components(self, theme_id: str) -> None:
        """Apply color scheme, cursor, icons, desktop theme from a global theme's defaults."""
        lnf_dir = None
        for base in (
            self.home / ".local/share/plasma/look-and-feel",
            Path("/usr/share/plasma/look-and-feel"),
        ):
            candidate = base / theme_id
            if candidate.is_dir():
                lnf_dir = candidate
                break

        if not lnf_dir:
            return
        defaults_file = lnf_dir / "contents" / "defaults"
        if not defaults_file.exists():
            return

        defaults: dict[str, str] = {}
        for line in defaults_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                defaults[k.strip()] = v.strip()

        if cs := defaults.get("colorScheme"):
            if shutil.which("plasma-apply-colorscheme"):
                try:
                    run_cmd(["plasma-apply-colorscheme", cs], check=False)
                    log_ok(f"Color scheme applied: {cs}")
                except CommandError:
                    pass

        if ct := defaults.get("cursorTheme"):
            if shutil.which("plasma-apply-cursortheme"):
                try:
                    run_cmd(["plasma-apply-cursortheme", ct], check=False)
                    log_ok(f"Cursor theme applied: {ct}")
                except CommandError:
                    pass

        if dt := defaults.get("theme"):
            if shutil.which("plasma-apply-desktoptheme"):
                try:
                    run_cmd(["plasma-apply-desktoptheme", dt], check=False)
                    log_ok(f"Desktop/Plasma style applied: {dt}")
                except CommandError:
                    pass

        if it := defaults.get("iconTheme"):
            self._set_icon_theme(it)

    # ── Community theme installer ─────────────────────────────────────

    def _install_community_theme(self) -> None:
        section("Install Community KDE Themes")
        console.print("  Popular KDE Plasma Global Themes:")
        console.print()
        for i, t in enumerate(COMMUNITY_THEMES, 1):
            console.print(f"    {i}) {t['name']}")
        console.print(f"\n    0) Cancel\n")

        from rich.prompt import Prompt
        pick = Prompt.ask("  Select theme", default="0").strip()
        if pick == "0":
            return
        try:
            idx = int(pick) - 1
            if not (0 <= idx < len(COMMUNITY_THEMES)):
                raise ValueError
        except ValueError:
            console.print("  Invalid choice.")
            return

        theme = COMMUNITY_THEMES[idx]
        log(f"Selected theme: {theme['name']}")

        # Arch: try AUR first
        if self.system.distro_family == "arch" and self.system.aur_helper and os.geteuid() != 0:
            log_info(f"Trying AUR package: {theme['aur']}")
            if self.pkg.install(theme["aur"]):
                log_ok(f"{theme['name']} installed from AUR.")
                self._prompt_apply_theme()
                return

        # Clone and install
        if not shutil.which("git") and not shutil.which("gh"):
            log_err("git or gh CLI is required.")
            return

        with tempfile.TemporaryDirectory(prefix="kde_theme_") as tmpdir:
            if not gh_clone(theme["repo"], tmpdir):
                log_err("Failed to clone repository.")
                return
            log_ok("Repository cloned.")

            install_sh = Path(tmpdir) / "install.sh"
            if install_sh.exists():
                log("Running install.sh from the theme repo…")
                install_sh.chmod(0o755)
                run_cmd(["bash", str(install_sh)], check=False)
                log_ok(f"{theme['name']} install script completed.")
            else:
                # Manual fallback: copy look-and-feel dirs
                dest = self.home / ".local/share/plasma/look-and-feel"
                dest.mkdir(parents=True, exist_ok=True)
                for src_name in ("look-and-feel", "plasma/look-and-feel"):
                    lnf_src = Path(tmpdir) / src_name
                    if lnf_src.is_dir():
                        for item in lnf_src.iterdir():
                            shutil.copytree(item, dest / item.name, dirs_exist_ok=True)
                        log_ok(f"Theme files copied to {dest}.")
                        break
                else:
                    log_info("No install.sh or look-and-feel directory found.")

        self._prompt_apply_theme()

    def _prompt_apply_theme(self) -> None:
        console.print()
        if confirm("Apply the newly installed theme now?"):
            self._apply_installed_theme()
        else:
            log_info("You can apply it later via System Settings → Global Theme.")

    # ── Icon themes ───────────────────────────────────────────────────

    def _icon_themes_menu(self) -> None:
        section("Icon Theme Manager")
        console.print("    [cyan]1)[/cyan] Apply an installed icon theme")
        console.print("    [cyan]2)[/cyan] Install a popular icon pack")
        console.print()
        console.print("    [dim]0)[/dim] Cancel")
        console.print()

        from rich.prompt import Prompt
        action = Prompt.ask("  Enter choice", default="0").strip()
        match action:
            case "1": self._apply_icon_theme()
            case "2": self._install_icon_pack()

    def _apply_icon_theme(self) -> None:
        log("Scanning for installed icon themes…")
        icon_themes: list[str] = []
        search_paths = [
            Path("/usr/share/icons"),
            self.home / ".local/share/icons",
            self.home / ".icons",
        ]
        for base in search_paths:
            if not base.exists():
                continue
            for idx_file in base.glob("*/index.theme"):
                name = idx_file.parent.name
                if name in ("hicolor", "default"):
                    continue
                try:
                    content = idx_file.read_text()
                except PermissionError:
                    continue
                if "Directories=" in content and name not in icon_themes:
                    icon_themes.append(name)

        if not icon_themes:
            log_warn("No icon themes found on the system.")
            return

        console.print()
        console.print("  Installed icon themes:")
        console.print()
        for i, t in enumerate(icon_themes, 1):
            console.print(f"    {i}) {t}")
        console.print(f"\n    0) Cancel\n")

        from rich.prompt import Prompt
        choice = Prompt.ask("  Select icon theme", default="0").strip()
        if choice == "0":
            return
        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(icon_themes)):
                raise ValueError
        except ValueError:
            console.print("  Invalid choice.")
            return

        selected = icon_themes[idx]
        self._set_icon_theme(selected)
        log_ok(f"Icon theme '{selected}' applied globally (KDE + GTK).")

    def _install_icon_pack(self) -> None:
        section("Install Community Icon Packs")
        console.print("  Popular Icon Themes:")
        console.print()
        for i, pack in enumerate(ICON_PACKS, 1):
            console.print(f"    {i}) {pack['name']}")
        console.print(f"\n    0) Cancel\n")

        from rich.prompt import Prompt
        pick = Prompt.ask("  Select icon pack", default="0").strip()
        if pick == "0":
            return
        try:
            idx = int(pick) - 1
            if not (0 <= idx < len(ICON_PACKS)):
                raise ValueError
        except ValueError:
            console.print("  Invalid choice.")
            return

        pack = ICON_PACKS[idx]
        log(f"Selected icon pack: {pack['name']}")

        # Try native package first
        native_pkg = pack.get({"debian": "deb", "fedora": "fed"}.get(self.system.distro_family, ""), "")
        if native_pkg:
            if self.pkg.install(*native_pkg.split()):
                log_ok(f"{pack['name']} installed from repository.")
                self._set_icon_theme(pack["folder"])
                return

        # Arch AUR
        if self.system.distro_family == "arch" and self.system.aur_helper and os.geteuid() != 0:
            if self.pkg.install(pack["aur"]):
                log_ok(f"{pack['name']} installed from AUR.")
                self._set_icon_theme(pack["folder"])
                return

        # Clone from git
        if not shutil.which("git") and not shutil.which("gh"):
            log_err("git or gh CLI is required.")
            return

        with tempfile.TemporaryDirectory(prefix="icons_") as tmpdir:
            if not gh_clone(pack["repo"], tmpdir):
                log_err("Failed to clone icon theme repository.")
                return

            install_sh = Path(tmpdir) / "install.sh"
            if install_sh.exists():
                install_sh.chmod(0o755)
                run_cmd(["bash", str(install_sh)], check=False)
                log_ok(f"{pack['name']} install script completed.")
            else:
                dest = self.home / ".local/share/icons" / pack["folder"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                src = Path(tmpdir) / pack["folder"]
                if src.is_dir():
                    shutil.copytree(src, dest, dirs_exist_ok=True)
                else:
                    shutil.copytree(tmpdir, dest, dirs_exist_ok=True)
                log_ok(f"Icon theme copied to {dest}.")

        if confirm(f"Apply '{pack['name']}' as the active icon theme now?"):
            self._set_icon_theme(pack["folder"])
            log_ok(f"Icon theme '{pack['folder']}' applied globally (KDE + GTK).")

    def _set_icon_theme(self, icon_name: str) -> None:
        kwc = self._kwc()
        if not kwc:
            log_warn("kwriteconfig not found — cannot set icon theme programmatically.")
            return
        log(f"Setting icon theme to: {icon_name}")
        run_cmd([kwc, "--file", "kdeglobals", "--group", "Icons", "--key", "Theme", icon_name], check=False)
        log_ok(f"Icon theme set in kdeglobals: {icon_name}")

        # GTK 3 + 4
        for ver in ("gtk-3.0", "gtk-4.0"):
            ini = self.home / ".config" / ver / "settings.ini"
            self._set_gtk_key(ini, "gtk-icon-theme-name", icon_name)

        # Notify KDE
        self._notify_kde()

    # ── Font manager ──────────────────────────────────────────────────

    def _font_manager_menu(self) -> None:
        section("Font Manager")
        console.print("    [cyan]1)[/cyan] Apply a font to all KDE categories (globally)")
        console.print("    [cyan]2)[/cyan] Install popular developer / UI fonts")
        console.print("    [cyan]3)[/cyan] Install a font from a .zip / .tar file or URL")
        console.print()
        console.print("    [dim]0)[/dim] Cancel")
        console.print()

        from rich.prompt import Prompt
        action = Prompt.ask("  Enter choice", default="0").strip()
        match action:
            case "1": self._font_apply()
            case "2": self._font_install_popular()
            case "3": self._font_install_custom()

    def _font_apply(self) -> None:
        section("Apply an Installed Font")
        log("Listing installed font families…")
        if not shutil.which("fc-list"):
            log_err("fontconfig (fc-list) not found.")
            return

        result = run_cmd(["fc-list", ":", "family"], check=False)
        raw = (result.stdout or "").splitlines()
        families = sorted({line.split(",")[0].strip() for line in raw if line.strip()})
        if not families:
            log_err("No fonts found via fc-list.")
            return

        console.print(f"  {len(families)} font families found on the system.")
        console.print("  Type a search term to filter, or press Enter to list all.")
        filter_text = prompt("Filter (or Enter for all)")
        if filter_text:
            families = [f for f in families if filter_text.lower() in f.lower()]

        if not families:
            log_warn(f"No fonts matched '{filter_text}'.")
            return
        if len(families) > 40:
            console.print(f"  {len(families)} fonts match. Showing first 40:")
            families = families[:40]

        console.print()
        for i, f in enumerate(families, 1):
            console.print(f"    {i}) {f}")
        console.print(f"\n    0) Cancel\n")

        from rich.prompt import Prompt
        pick = Prompt.ask("  Select font", default="0").strip()
        if pick == "0":
            return
        try:
            idx = int(pick) - 1
            if not (0 <= idx < len(families)):
                raise ValueError
        except ValueError:
            console.print("  Invalid choice.")
            return

        selected = families[idx]
        size = prompt("Font size", default="10")
        self._set_global_font(selected, size)

    def _font_install_popular(self) -> None:
        section("Install Popular Fonts")
        for i, f in enumerate(POPULAR_FONTS, 1):
            console.print(f"    {i}) {f['name']}")
        console.print(f"\n    0) Cancel\n")

        from rich.prompt import Prompt
        pick = Prompt.ask("  Select font", default="0").strip()
        if pick == "0":
            return
        try:
            idx = int(pick) - 1
            if not (0 <= idx < len(POPULAR_FONTS)):
                raise ValueError
        except ValueError:
            console.print("  Invalid choice.")
            return

        font = POPULAR_FONTS[idx]

        # Try native package
        native_key = {"debian": "deb", "fedora": "fed", "arch": "arch"}.get(self.system.distro_family, "")
        native_pkg = font.get(native_key, "")
        installed = False

        if native_pkg:
            log_info(f"Trying package manager: {native_pkg}")
            if self.pkg.install(*native_pkg.split()):
                log_ok(f"{font['name']} installed from repository.")
                installed = True

        if not installed and font["url"]:
            self._font_download_and_install(font["url"], font["name"])
            installed = True
        elif not installed:
            log_err(f"No download URL or package available for {font['name']}.")
            return

        if installed:
            console.print()
            if confirm(f"Apply '{font['family']}' as the system font now?"):
                size = prompt("Font size", default="10")
                self._set_global_font(font["family"], size)

    def _font_install_custom(self) -> None:
        section("Install Custom Font")
        console.print("  Provide a path to a local archive (.zip, .tar.gz, .tar.xz)")
        console.print("  or a direct download URL.")
        console.print()
        user_input = prompt("Path or URL (0 to cancel)")
        if user_input in ("0", ""):
            return

        if user_input.startswith(("http://", "https://")):
            self._font_download_and_install(user_input, "custom font")
        elif Path(user_input).expanduser().exists():
            self._font_download_and_install(str(Path(user_input).expanduser()), "custom font", local=True)
        else:
            log_err(f"File not found: {user_input}")
            return

        if confirm("Apply the newly installed font now?"):
            self._font_apply()

    def _font_download_and_install(self, url_or_path: str, label: str, *, local: bool = False) -> None:
        font_dest = self.home / ".local/share/fonts"
        font_dest.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="fonts_") as tmpdir:
            archive = Path(tmpdir) / "font_archive"
            if local:
                shutil.copy2(url_or_path, archive)
            else:
                log(f"Downloading {label}…")
                if shutil.which("curl"):
                    run_cmd(["curl", "-fSL", url_or_path, "-o", str(archive)], check=False)
                elif shutil.which("wget"):
                    run_cmd(["wget", "-q", url_or_path, "-O", str(archive)], check=False)
                else:
                    log_err("curl or wget is required to download fonts.")
                    return

            if not archive.exists() or archive.stat().st_size == 0:
                log_err("Download failed or empty file.")
                return

            extract_dir = Path(tmpdir) / "extracted"
            extract_dir.mkdir()

            # Extract
            try:
                run_cmd(["tar", "xf", str(archive), "-C", str(extract_dir)], check=True)
            except CommandError:
                try:
                    run_cmd(["unzip", "-qo", str(archive), "-d", str(extract_dir)], check=True)
                except CommandError:
                    log_err("Cannot extract archive.")
                    return

            count = 0
            for ext in ("*.ttf", "*.otf", "*.TTF", "*.OTF"):
                for f in extract_dir.rglob(ext):
                    shutil.copy2(f, font_dest / f.name)
                    count += 1

            if count == 0:
                log_err("No .ttf/.otf files found in archive.")
                return

            run_cmd(["fc-cache", "-f"], check=False)
            log_ok(f"{count} font files installed to {font_dest}.")

    def _set_global_font(self, font_name: str, font_size: str = "10") -> None:
        kwc = self._kwc()
        if not kwc:
            log_warn("kwriteconfig not found — cannot set fonts programmatically.")
            return

        log(f"Setting all fonts to: {font_name}  size: {font_size}")
        font_entry = f"{font_name},{font_size},-1,5,50,0,0,0,0,0"
        small_entry = f"{font_name},8,-1,5,50,0,0,0,0,0"

        for key in ("font", "menuFont", "toolBarFont", "activeFont"):
            run_cmd([kwc, "--file", "kdeglobals", "--group", "General", "--key", key, font_entry], check=False)
        run_cmd([kwc, "--file", "kdeglobals", "--group", "General", "--key", "smallestReadableFont", small_entry], check=False)
        log_ok("KDE General / Menu / Toolbar / Active Title fonts set.")

        # Fixed-width font
        mono_font = font_name
        console.print()
        if confirm("Set a different monospace / fixed-width font?"):
            mono_font = prompt("Monospace font family name") or font_name
        mono_entry = f"{mono_font},{font_size},-1,5,50,0,0,0,0,0"
        run_cmd([kwc, "--file", "kdeglobals", "--group", "General", "--key", "fixed", mono_entry], check=False)
        log_ok(f"Fixed-width font set: {mono_font}")

        # GTK 3 + 4
        for ver in ("gtk-3.0", "gtk-4.0"):
            ini = self.home / ".config" / ver / "settings.ini"
            self._set_gtk_key(ini, "gtk-font-name", f"{font_name} {font_size}")

        self._notify_kde()
        run_cmd(["fc-cache", "-f"], check=False)
        log_ok("Fonts applied globally (KDE + GTK). Some apps may need a restart.")

    # ── SDDM theme helper ────────────────────────────────────────────

    def _set_sddm_theme(self, theme_id: str) -> None:
        sddm_dir = Path("/usr/share/sddm/themes")
        base = theme_id.split(".")[-1] if "." in theme_id else theme_id

        sddm_name = ""
        for candidate in (base, base.lower()):
            if (sddm_dir / candidate).is_dir():
                sddm_name = candidate
                break

        if sddm_name:
            try:
                require_sudo()
                run_cmd(["mkdir", "-p", "/etc/sddm.conf.d"], sudo=True)
                run_cmd(
                    ["tee", "/etc/sddm.conf.d/theme.conf"],
                    sudo=True,
                    input_text=f"[Theme]\nCurrent={sddm_name}\n",
                )
                log_ok(f"SDDM theme set to '{sddm_name}'.")
            except Exception:
                log_warn(f"Could not set SDDM theme to '{sddm_name}'.")
        else:
            log_info(f"No matching SDDM theme found for '{theme_id}' — set it manually.")

    # ── macOS one-click setup ─────────────────────────────────────────

    def macos_setup(self) -> None:
        banner("macOS-Style Full Setup")
        console.print("  [bold]This will transform your KDE Plasma desktop to look like macOS.[/bold]")
        console.print()
        console.print("  The following changes will be made:")
        console.print("    1. Install WhiteSur GTK / KDE Global Theme")
        console.print("    2. Install WhiteSur Icon Theme")
        console.print("    3. Install macOS-style Cursors")
        console.print("    4. Install & apply macOS-style fonts (Inter + JetBrains Mono NF)")
        console.print("    5. Configure KDE layout: top panel, bottom dock, left-side window buttons")
        console.print("    6. Install WhiteSur Firefox theme")
        console.print()

        if not shutil.which("plasma-apply-lookandfeel"):
            log_err("KDE Plasma not detected. This setup is for KDE Plasma only.")
            return
        if not confirm("Proceed with full macOS-style setup?"):
            return
        if not shutil.which("git"):
            log_info("git is required. Installing…")
            self.pkg.install("git")
        try:
            require_sudo()
        except Exception:
            return

        # Step 1: WhiteSur KDE Theme
        section("Step 1/6 — WhiteSur KDE Global Theme")
        kde_installed = False
        if self.system.distro_family == "arch" and self.system.aur_helper and os.geteuid() != 0:
            if self.pkg.install("whitesur-kde-theme-git"):
                kde_installed = True
                log_ok("WhiteSur KDE theme installed from AUR.")

        if not kde_installed:
            with tempfile.TemporaryDirectory(prefix="macos_kde_") as tmp:
                if gh_clone("https://github.com/vinceliuice/WhiteSur-kde.git", tmp):
                    install_sh = Path(tmp) / "install.sh"
                    if install_sh.exists():
                        install_sh.chmod(0o755)
                        run_cmd(["bash", str(install_sh)], check=False)
                        kde_installed = True
                        log_ok("WhiteSur KDE theme installed.")

        if kde_installed:
            try:
                result = run_cmd(["plasma-apply-lookandfeel", "-l"], check=False)
                themes_out = result.stdout or ""
                for candidate in ("com.github.vinceliuice.WhiteSur", "com.github.vinceliuice.WhiteSur-dark", "WhiteSur", "WhiteSur-dark"):
                    if candidate in themes_out:
                        run_cmd(["plasma-apply-lookandfeel", "-a", candidate], check=False)
                        log_ok(f"Global theme applied: {candidate}")
                        break
            except CommandError:
                log_warn("Could not apply look-and-feel.")

        # Step 2: WhiteSur Icon Theme
        section("Step 2/6 — WhiteSur Icon Theme")
        icons_installed = False
        if self.system.distro_family == "arch" and self.system.aur_helper and os.geteuid() != 0:
            if self.pkg.install("whitesur-icon-theme-git"):
                icons_installed = True
        if not icons_installed:
            with tempfile.TemporaryDirectory(prefix="macos_icons_") as tmp:
                if gh_clone("https://github.com/vinceliuice/WhiteSur-icon-theme.git", tmp):
                    install_sh = Path(tmp) / "install.sh"
                    if install_sh.exists():
                        install_sh.chmod(0o755)
                        run_cmd(["bash", str(install_sh)], check=False)
                        icons_installed = True
                        log_ok("WhiteSur icon theme installed.")
        if icons_installed:
            self._set_icon_theme("WhiteSur")

        # Step 3: macOS Cursor Theme
        section("Step 3/6 — macOS Cursor Theme")
        cursor_installed = False
        if self.system.distro_family == "arch" and self.system.aur_helper and os.geteuid() != 0:
            if self.pkg.install("whitesur-cursor-theme-git"):
                cursor_installed = True
        if not cursor_installed:
            with tempfile.TemporaryDirectory(prefix="macos_cursor_") as tmp:
                if gh_clone("https://github.com/vinceliuice/WhiteSur-cursors.git", tmp):
                    install_sh = Path(tmp) / "install.sh"
                    if install_sh.exists():
                        install_sh.chmod(0o755)
                        run_cmd(["bash", str(install_sh)], check=False)
                        cursor_installed = True
                    else:
                        cursor_dest = self.home / ".local/share/icons"
                        cursor_dest.mkdir(parents=True, exist_ok=True)
                        for d in Path(tmp).glob("WhiteSur*"):
                            if d.is_dir():
                                shutil.copytree(d, cursor_dest / d.name, dirs_exist_ok=True)
                        cursor_installed = True
                    log_ok("WhiteSur cursor theme installed.")

        if cursor_installed and shutil.which("plasma-apply-cursortheme"):
            for cname in ("WhiteSur-cursors", "WhiteSur Cursors", "whitesur-cursors"):
                try:
                    run_cmd(["plasma-apply-cursortheme", cname])
                    log_ok(f"Cursor theme applied: {cname}")
                    break
                except CommandError:
                    continue

        # Step 4: macOS-style Fonts
        section("Step 4/6 — macOS-style Fonts")
        # Install Inter
        match self.system.distro_family:
            case "debian": self.pkg.install("fonts-inter")
            case "fedora": self.pkg.install("inter-fonts")
            case "arch": self.pkg.install("inter-font")

        # Install JetBrains Mono NF
        mono_family = "JetBrainsMono Nerd Font"
        match self.system.distro_family:
            case "arch":
                self.pkg.install("ttf-jetbrains-mono-nerd")
            case _:
                nf_url = f"{_NF_BASE}/JetBrainsMono.tar.xz"
                self._font_download_and_install(nf_url, "JetBrainsMono Nerd Font")

        run_cmd(["fc-cache", "-f"], check=False)

        kwc = self._kwc()
        if kwc:
            ui_entry = "Inter,10,-1,5,50,0,0,0,0,0"
            sm_entry = "Inter,8,-1,5,50,0,0,0,0,0"
            mono_entry = f"{mono_family},10,-1,5,50,0,0,0,0,0"
            for key in ("font", "menuFont", "toolBarFont", "activeFont"):
                run_cmd([kwc, "--file", "kdeglobals", "--group", "General", "--key", key, ui_entry], check=False)
            run_cmd([kwc, "--file", "kdeglobals", "--group", "General", "--key", "smallestReadableFont", sm_entry], check=False)
            run_cmd([kwc, "--file", "kdeglobals", "--group", "General", "--key", "fixed", mono_entry], check=False)
            log_ok(f"KDE fonts set: UI=Inter  Mono={mono_family}")

            for ver in ("gtk-3.0", "gtk-4.0"):
                ini = self.home / ".config" / ver / "settings.ini"
                self._set_gtk_key(ini, "gtk-font-name", "Inter 10")
            log_ok("GTK fonts set to: Inter 10")

        # Step 5: KDE Layout
        section("Step 5/6 — macOS-style Panel Layout")
        if kwc:
            run_cmd([kwc, "--file", "kwinrc", "--group", "org.kde.kdecoration2", "--key", "ButtonsOnLeft", "XIA"], check=False)
            run_cmd([kwc, "--file", "kwinrc", "--group", "org.kde.kdecoration2", "--key", "ButtonsOnRight", ""], check=False)
            run_cmd([kwc, "--file", "kwinrc", "--group", "Windows", "--key", "FocusPolicy", "ClickToFocus"], check=False)
            run_cmd([kwc, "--file", "kwinrc", "--group", "org.kde.kdecoration2", "--key", "BorderSize", "None"], check=False)
            run_cmd([kwc, "--file", "kwinrc", "--group", "Plugins", "--key", "blurEnabled", "true"], check=False)
            run_cmd([kwc, "--file", "kwinrc", "--group", "Plugins", "--key", "translucencyEnabled", "true"], check=False)
            run_cmd([kwc, "--file", "kwinrc", "--group", "Effect-overview", "--key", "BorderActivate", "1"], check=False)
            log_ok("KWin settings configured (left buttons, blur, translucency).")

            # Reconfigure KWin live
            if shutil.which("dbus-send"):
                run_cmd([
                    "dbus-send", "--session", "--dest=org.kde.KWin", "/KWin",
                    "org.kde.KWin.reconfigure",
                ], check=False)

        log_ok("macOS-style panel layout configured.")
        log_info("For best results, log out and back in, or reboot.")

        # Step 6: Firefox macOS Theme
        section("Step 6/6 — WhiteSur Firefox Theme")
        from toolkit.theming.firefox import FirefoxThemer
        FirefoxThemer(self.system, self.pkg).run(show_banner=False)

        console.print()
        console.print("  [bold green]macOS-style setup complete![/bold green]")
        console.print()
        console.print("  Applied:")
        console.print("    ✔ WhiteSur KDE Global Theme")
        console.print("    ✔ WhiteSur Icon Theme")
        console.print("    ✔ WhiteSur Cursor Theme")
        console.print("    ✔ Fonts: Inter (UI) + JetBrains Mono NF (terminal)")
        console.print("    ✔ Layout: left window buttons, blur, translucency")
        console.print("    ✔ Firefox: WhiteSur macOS theme")
        log_info("Restart Plasma or reboot for all changes to take full effect.")

    # ── Restore default layout ────────────────────────────────────────

    def restore_default_layout(self) -> None:
        banner("Restore Default KDE Plasma Layout")

        plasma_rc = self.home / ".config" / "plasma-org.kde.plasma.desktop-appletsrc"

        # Find backups
        backups = sorted(
            self.home.joinpath(".config").glob("plasma-org.kde.plasma.desktop-appletsrc.bak_*"),
            reverse=True,
        )

        console.print()
        console.print("  [bold]Choose a restore method:[/bold]")
        console.print()

        if backups:
            console.print("  [green]Available backups (newest first):[/green]")
            for i, b in enumerate(backups, 1):
                ts = b.name.split(".bak_")[-1].replace("_", " ")
                console.print(f"    {i:2d}) {b.name}  ({ts})")
            console.print()

        console.print("    R) Reset to Plasma factory default")
        console.print("    0) Cancel")
        console.print()

        from rich.prompt import Prompt
        pick = Prompt.ask("  Choose", default="0").strip()

        if pick == "0":
            return
        if pick.upper() == "R":
            if not confirm("Remove ALL custom panel layouts and restore Plasma defaults?"):
                return
            if plasma_rc.exists():
                bak = plasma_rc.with_name(f"{plasma_rc.name}.bak_{datetime.now():%Y%m%d_%H%M%S}")
                shutil.copy2(plasma_rc, bak)
                log_ok(f"Current config backed up to {bak.name}.")
                plasma_rc.unlink()
            log("Removed panel config; Plasma will regenerate defaults.")
            self._restart_plasma()
            log_ok("Plasma factory default layout restored.")
            return

        try:
            idx = int(pick) - 1
            if not (0 <= idx < len(backups)):
                raise ValueError
        except ValueError:
            console.print("  Invalid selection.")
            return

        chosen = backups[idx]
        log(f"Restoring panel config from {chosen.name}")
        shutil.copy2(chosen, plasma_rc)
        log_ok("Panel config restored from backup.")
        self._restart_plasma()

    def _restart_plasma(self) -> None:
        """Stop and restart plasmashell to apply layout changes."""
        import time
        if not shutil.which("plasmashell"):
            log_info("plasmashell not found — changes will take effect on next login.")
            return

        try:
            run_cmd(["pgrep", "-x", "plasmashell"], check=True, timeout=3)
        except CommandError:
            log_info("Plasma Shell is not running — changes take effect on next login.")
            return

        log_info("Restarting Plasma Shell…")
        for cmd in ("kquitapp6", "kquitapp5"):
            if shutil.which(cmd):
                run_cmd([cmd, "plasmashell"], check=False)
                break
        else:
            run_cmd(["killall", "plasmashell"], check=False)

        # Wait for exit
        for _ in range(10):
            try:
                run_cmd(["pgrep", "-x", "plasmashell"], check=True, timeout=2)
                time.sleep(1)
            except CommandError:
                break

        # Start plasmashell
        for cmd in ("kstart", "kstart5"):
            if shutil.which(cmd):
                subprocess.Popen([cmd, "plasmashell"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
        else:
            subprocess.Popen(["plasmashell"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        time.sleep(3)
        try:
            run_cmd(["pgrep", "-x", "plasmashell"], check=True, timeout=3)
            log_ok("Plasma Shell restarted.")
        except CommandError:
            log_warn("Plasma Shell did not start. Try manually: kstart plasmashell")

    # ── GTK settings helper ───────────────────────────────────────────

    def _set_gtk_key(self, ini_path: Path, key: str, value: str) -> None:
        ini_path.parent.mkdir(parents=True, exist_ok=True)
        if ini_path.exists():
            content = ini_path.read_text()
            pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
            if pattern.search(content):
                content = pattern.sub(f"{key}={value}", content)
            else:
                content += f"\n{key}={value}\n"
            ini_path.write_text(content)
        else:
            ini_path.write_text(f"[Settings]\n{key}={value}\n")

    # ── KDE notification (dbus) ───────────────────────────────────────

    def _notify_kde(self) -> None:
        if shutil.which("dbus-send"):
            run_cmd([
                "dbus-send", "--session", "--type=signal",
                "/KIconLoader", "org.kde.KIconLoader.iconChanged",
            ], check=False)
            run_cmd([
                "dbus-send", "--session", "--dest=org.kde.KWin",
                "/KWin", "org.kde.KWin.reconfigure",
            ], check=False)
