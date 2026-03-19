"""Firefox WhiteSur macOS-style theme installer.

Finds Firefox profiles across native, Snap, and Flatpak installs,
clones WhiteSur-firefox-theme, runs install.sh with appropriate options,
and enables the toolkit.legacyUserProfileCustomizations.stylesheets pref.
"""

from __future__ import annotations

import json
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
    section,
    banner,
)
from toolkit.util import CommandError, gh_clone, run_cmd

_PROFILE_ROOTS = [
    Path.home() / ".mozilla/firefox",
    Path.home() / "snap/firefox/common/.mozilla/firefox",
    Path.home() / ".var/app/org.mozilla.firefox/.mozilla/firefox",
]

REPO_URL = "https://github.com/nicholasgasior/WhiteSur-firefox-theme.git"
UPSTREAM_URL = "https://github.com/nicholasgasior/WhiteSur-firefox-theme.git"


class FirefoxThemer:
    """WhiteSur Firefox macOS theme installer."""

    def __init__(self, system: SystemDetect, pkg: PackageManager) -> None:
        self.system = system
        self.pkg = pkg

    def run(self, *, show_banner: bool = True) -> None:
        if show_banner:
            banner("Firefox macOS Theme (WhiteSur)")

        profiles = self._find_profiles()
        if not profiles:
            log_warn("No Firefox profiles found.")
            log_info("Searched: " + ", ".join(str(p) for p in _PROFILE_ROOTS))
            return

        console.print(f"  Found {len(profiles)} Firefox profile(s):")
        for i, (root, name) in enumerate(profiles, 1):
            console.print(f"    {i}) {root.name}/{name}")
        console.print()

        if not confirm("Install WhiteSur macOS theme for all profiles?"):
            return

        if not shutil.which("git") and not shutil.which("gh"):
            log_err("git or gh CLI is required.")
            return

        with tempfile.TemporaryDirectory(prefix="firefox_theme_") as tmpdir:
            if not gh_clone(UPSTREAM_URL, tmpdir):
                log_err("Failed to clone WhiteSur-firefox-theme.")
                return

            install_sh = Path(tmpdir) / "install.sh"
            if install_sh.exists():
                install_sh.chmod(0o755)
                log("Running WhiteSur Firefox theme installer…")
                run_cmd(["bash", str(install_sh)], check=False, capture=False)
                log_ok("WhiteSur Firefox theme installed via script.")
            else:
                # Manual install: copy chrome dirs into profiles
                for root, profile_name in profiles:
                    self._manual_install(Path(tmpdir), root / profile_name)

        # Enable userChrome.css support in each profile
        for root, profile_name in profiles:
            self._enable_userchrome(root / profile_name)

        log_ok("Firefox theme setup complete. Restart Firefox to see changes.")

    def _find_profiles(self) -> list[tuple[Path, str]]:
        """Return list of (profile_root, profile_dir_name) for all Firefox installs."""
        profiles: list[tuple[Path, str]] = []
        for root in _PROFILE_ROOTS:
            if not root.is_dir():
                continue
            ini = root / "profiles.ini"
            if not ini.exists():
                continue
            # Parse profiles.ini
            import configparser
            cfg = configparser.ConfigParser()
            cfg.read(str(ini))
            for section_name in cfg.sections():
                if not section_name.startswith("Profile"):
                    continue
                path = cfg.get(section_name, "Path", fallback="")
                is_relative = cfg.getint(section_name, "IsRelative", fallback=1)
                if not path:
                    continue
                if is_relative:
                    full = root / path
                else:
                    full = Path(path)
                if full.is_dir():
                    profiles.append((root, path))
        return profiles

    def _manual_install(self, theme_dir: Path, profile_dir: Path) -> None:
        """Manually copy chrome/userChrome.css into a profile."""
        chrome_src = theme_dir / "chrome"
        if not chrome_src.is_dir():
            # Some forks put it in a subfolder
            for candidate in theme_dir.rglob("userChrome.css"):
                chrome_src = candidate.parent
                break
            else:
                log_warn(f"No chrome/userChrome.css found in theme repo.")
                return

        chrome_dest = profile_dir / "chrome"
        chrome_dest.mkdir(exist_ok=True)
        shutil.copytree(chrome_src, chrome_dest, dirs_exist_ok=True)
        log_ok(f"Theme files copied to {chrome_dest}")

    def _enable_userchrome(self, profile_dir: Path) -> None:
        """Enable toolkit.legacyUserProfileCustomizations.stylesheets in user.js."""
        prefs_key = "toolkit.legacyUserProfileCustomizations.stylesheets"
        user_js = profile_dir / "user.js"

        if user_js.exists():
            content = user_js.read_text()
            if prefs_key in content:
                log_info(f"userChrome support already enabled in {profile_dir.name}")
                return
            content += f'\nuser_pref("{prefs_key}", true);\n'
            user_js.write_text(content)
        else:
            user_js.write_text(f'user_pref("{prefs_key}", true);\n')
        log_ok(f"userChrome CSS support enabled for {profile_dir.name}")
