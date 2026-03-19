"""Web Development Setup Wizard — React, PHP, Tailwind CSS, Database engines.

Handles:
- Node.js (v24 LTS via nvm) + React project scaffolding
- PHP + Composer installation
- Tailwind CSS setup
- Database engines (MariaDB, MySQL, PostgreSQL, MongoDB)
- Cross-platform support (Linux + Windows basic)
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from toolkit.database import DatabaseSetup
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
    press_enter,
    status_icon,
)
from toolkit.util import CommandError, IS_WINDOWS, run_cmd, require_sudo

# ── Node.js target version ────────────────────────────────────────────

NODE_LTS_VERSION = "24"

# ── PHP package mappings ──────────────────────────────────────────────

_PHP_MAP: dict[str, str] = {
    "debian": "php php-cli php-mbstring php-xml php-curl php-zip php-mysql php-pgsql unzip",
    "fedora": "php php-cli php-mbstring php-xml php-curl php-zip php-mysqlnd php-pgsql unzip",
    "arch":   "php php-cgi php-gd php-intl unzip",
}


class WebDevSetup:
    """Interactive web development environment setup wizard."""

    def __init__(self, system: SystemDetect, pkg: PackageManager) -> None:
        self.system = system
        self.pkg = pkg
        self.db = DatabaseSetup(system, pkg)

    def run(self) -> None:
        banner("Web Development Setup Wizard")
        console.print("  [bold]Select what to set up:[/bold]")
        console.print()
        console.print("    [cyan]1)[/cyan] Node.js (v24 LTS) + React Project")
        console.print("    [cyan]2)[/cyan] PHP + Composer")
        console.print("    [cyan]3)[/cyan] Tailwind CSS (add to existing project)")
        console.print("    [cyan]4)[/cyan] Full React Stack (Node + React + Tailwind)")
        console.print("    [cyan]5)[/cyan] Database Engine (MariaDB / MySQL / PostgreSQL / MongoDB)")
        console.print("    [cyan]6)[/cyan] Full Stack Setup (Node + React + Tailwind + PHP + DB)")
        console.print()
        console.print("    [dim]0)[/dim] Back to main menu")
        console.print()

        from rich.prompt import Prompt
        choice = Prompt.ask("  Enter choice", default="0").strip()

        match choice:
            case "1": self._setup_node_react()
            case "2": self._setup_php()
            case "3": self._setup_tailwind()
            case "4": self._full_react_stack()
            case "5": self._database_menu()
            case "6": self._full_stack()
            case _:   return

        press_enter()

    # ══════════════════════════════════════════════════════════════════
    #  Node.js + React
    # ══════════════════════════════════════════════════════════════════

    def _setup_node_react(self) -> None:
        self._ensure_node()
        console.print()
        if confirm("Scaffold a new React project?"):
            self._scaffold_react()

    def _ensure_node(self) -> bool:
        """Install Node.js v24 LTS via nvm (preferred) or system packages.

        Returns True if Node.js is available after this step.
        """
        section("Node.js Setup")

        node_path = shutil.which("node")
        if node_path:
            ver = self._get_node_version()
            log_ok(f"Node.js found: {ver}")
            if not ver.startswith(f"v{NODE_LTS_VERSION}"):
                log_warn(f"Current version is {ver} — target is v{NODE_LTS_VERSION} LTS.")
                if not confirm(f"Install Node.js v{NODE_LTS_VERSION} via nvm alongside current version?"):
                    log_info("Keeping current Node.js version.")
                    return True
                return self._install_node_nvm()
            return True

        log_warn("Node.js is not installed.")
        console.print()
        console.print("  [bold]Installation method:[/bold]")
        console.print(f"    [cyan]1)[/cyan] nvm (recommended — manages multiple Node versions)")
        console.print(f"    [cyan]2)[/cyan] System package manager")
        console.print(f"    [dim]0)[/dim] Skip")
        console.print()

        from rich.prompt import Prompt
        method = Prompt.ask("  Enter choice", default="1").strip()

        match method:
            case "1":
                return self._install_node_nvm()
            case "2":
                return self._install_node_system()
            case _:
                return False

    def _get_node_version(self) -> str:
        try:
            r = run_cmd(["node", "--version"], check=False)
            return (r.stdout or "").strip()
        except CommandError:
            return "unknown"

    def _install_node_nvm(self) -> bool:
        """Install nvm and Node.js v24 LTS."""
        section("Installing Node.js via nvm")

        nvm_dir = Path.home() / ".nvm"
        nvm_sh = nvm_dir / "nvm.sh"

        if not nvm_sh.exists():
            log("Installing nvm…")
            if not shutil.which("curl") and not shutil.which("wget"):
                log_err("curl or wget is required to install nvm.")
                return False
            try:
                if shutil.which("curl"):
                    run_cmd([
                        "bash", "-c",
                        "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
                    ], check=True, capture=False)
                else:
                    run_cmd([
                        "bash", "-c",
                        "wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
                    ], check=True, capture=False)
                log_ok("nvm installed.")
            except CommandError:
                log_err("Failed to install nvm.")
                return False

        # Install Node.js via nvm
        log(f"Installing Node.js v{NODE_LTS_VERSION} via nvm…")
        nvm_cmd = f'source "{nvm_sh}" && nvm install {NODE_LTS_VERSION} && nvm alias default {NODE_LTS_VERSION}'
        try:
            run_cmd(["bash", "-c", nvm_cmd], check=True, capture=False)
            log_ok(f"Node.js v{NODE_LTS_VERSION} installed and set as default.")
            log_info("Run 'source ~/.nvm/nvm.sh' or open a new terminal to use it.")
            return True
        except CommandError:
            log_err(f"Failed to install Node.js v{NODE_LTS_VERSION} via nvm.")
            return False

    def _install_node_system(self) -> bool:
        """Install Node.js via the system package manager."""
        log("Installing Node.js via system package manager…")
        try:
            require_sudo()
        except Exception:
            return False

        if self.pkg.install("nodejs", "npm"):
            ver = self._get_node_version()
            log_ok(f"Node.js installed: {ver}")
            log_warn(f"System repos may not have v{NODE_LTS_VERSION}. Consider nvm for version control.")
            return True
        log_err("Node.js installation failed.")
        return False

    def _scaffold_react(self) -> None:
        """Create a new React project via Vite."""
        section("Scaffold React Project")

        project_name = prompt("Project name", default="my-react-app")
        if not project_name:
            return

        target = Path.cwd() / project_name
        if target.exists():
            log_warn(f"Directory '{project_name}' already exists.")
            if not confirm("Overwrite?"):
                return

        console.print()
        console.print("  [bold]Template:[/bold]")
        console.print("    [cyan]1)[/cyan] React (JavaScript)")
        console.print("    [cyan]2)[/cyan] React + TypeScript")
        console.print()

        from rich.prompt import Prompt
        tpl = Prompt.ask("  Enter choice", default="2").strip()

        template = "react-ts" if tpl == "2" else "react"

        # Use the correct npm/npx path (nvm or system)
        npx = self._find_npx()
        if not npx:
            log_err("npx not found. Install Node.js first.")
            return

        log(f"Creating React project: {project_name} (template: {template})")
        try:
            run_cmd(
                [npx, "create-vite@latest", project_name, "--template", template],
                check=True,
                capture=False,
            )
            log_ok(f"React project created at ./{project_name}")
        except CommandError:
            log_err("Project scaffolding failed.")
            return

        # Install dependencies
        npm = self._find_npm()
        if npm and confirm("Install npm dependencies now?"):
            log("Running npm install…")
            try:
                run_cmd([npm, "install"], check=True, capture=False)
            except CommandError:
                log_warn("npm install failed — you can run it manually later.")

        console.print()
        log_info(f"Next steps:")
        console.print(f"    cd {project_name}")
        console.print(f"    npm run dev")

    # ══════════════════════════════════════════════════════════════════
    #  PHP + Composer
    # ══════════════════════════════════════════════════════════════════

    def _setup_php(self) -> None:
        self._ensure_php()
        self._ensure_composer()

    def _ensure_php(self) -> bool:
        """Install PHP and common extensions."""
        section("PHP Setup")

        if shutil.which("php"):
            try:
                r = run_cmd(["php", "--version"], check=False)
                ver_line = (r.stdout or "").splitlines()[0] if r.stdout else "unknown"
                log_ok(f"PHP found: {ver_line}")
                return True
            except CommandError:
                pass

        log_warn("PHP is not installed.")
        if not confirm("Install PHP and common extensions?"):
            return False

        family = self.system.distro_family
        pkgs = _PHP_MAP.get(family, "")
        if not pkgs:
            if IS_WINDOWS:
                log_info("On Windows, install PHP from https://php.net or via Scoop/Choco:")
                console.print("    scoop install php")
                console.print("    choco install php")
                return False
            log_err(f"No PHP package mapping for '{family}'.")
            return False

        try:
            require_sudo()
        except Exception:
            return False

        if self.pkg.install(*pkgs.split()):
            log_ok("PHP installed.")
            return True
        log_err("PHP installation failed.")
        return False

    def _ensure_composer(self) -> bool:
        """Install Composer (PHP package manager)."""
        section("Composer Setup")

        if shutil.which("composer"):
            try:
                r = run_cmd(["composer", "--version"], check=False)
                log_ok(f"Composer found: {(r.stdout or '').strip()}")
                return True
            except CommandError:
                pass

        log_warn("Composer is not installed.")
        if not confirm("Install Composer?"):
            return False

        # Arch has a native package
        if self.system.distro_family == "arch":
            if self.pkg.install("composer"):
                log_ok("Composer installed from repos.")
                return True

        # Official installer
        if not shutil.which("php"):
            log_err("PHP is required to install Composer.")
            return False

        log("Downloading Composer installer…")
        try:
            run_cmd([
                "bash", "-c",
                "curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer"
            ], sudo=True, check=True, capture=False)
            log_ok("Composer installed to /usr/local/bin/composer.")
            return True
        except CommandError:
            log_err("Composer installation failed.")
            log_info("Manual install: https://getcomposer.org/download/")
            return False

    # ══════════════════════════════════════════════════════════════════
    #  Tailwind CSS
    # ══════════════════════════════════════════════════════════════════

    def _setup_tailwind(self) -> None:
        """Add Tailwind CSS to an existing project."""
        section("Tailwind CSS Setup")

        npm = self._find_npm()
        npx = self._find_npx()
        if not npm:
            log_warn("npm not found. Setting up Node.js first…")
            if not self._ensure_node():
                return
            npm = self._find_npm()
            npx = self._find_npx()
            if not npm:
                log_err("npm still not available.")
                return

        # Check if we're in a project with package.json
        pkg_json = Path.cwd() / "package.json"
        if not pkg_json.exists():
            log_warn("No package.json found in current directory.")
            console.print("  Tailwind CSS needs an existing npm project.")
            console.print("  Create a React project first (option 1 or 4), then run this.")
            return

        log("Installing Tailwind CSS v4…")
        try:
            run_cmd(
                [npm, "install", "tailwindcss", "@tailwindcss/vite"],
                check=True,
                capture=False,
            )
            log_ok("Tailwind CSS packages installed.")
        except CommandError:
            log_err("Failed to install Tailwind CSS.")
            return

        # Add @import to CSS
        css_candidates = [
            Path.cwd() / "src" / "index.css",
            Path.cwd() / "src" / "App.css",
            Path.cwd() / "src" / "styles" / "globals.css",
        ]

        css_file = None
        for c in css_candidates:
            if c.exists():
                css_file = c
                break

        tw_import = '@import "tailwindcss";'

        if css_file:
            content = css_file.read_text()
            if "tailwindcss" not in content:
                css_file.write_text(f"{tw_import}\n\n{content}")
                log_ok(f"Added Tailwind import to {css_file.relative_to(Path.cwd())}")
            else:
                log_ok("Tailwind import already present in CSS.")
        else:
            # Create src/index.css
            src_dir = Path.cwd() / "src"
            src_dir.mkdir(exist_ok=True)
            index_css = src_dir / "index.css"
            index_css.write_text(f"{tw_import}\n")
            log_ok("Created src/index.css with Tailwind import.")

        # Check if vite.config exists and add the plugin
        self._add_tailwind_vite_plugin()

        console.print()
        log_ok("Tailwind CSS v4 is ready.")
        log_info("Docs: https://tailwindcss.com/docs")

    def _add_tailwind_vite_plugin(self) -> None:
        """Add @tailwindcss/vite plugin to vite.config if present."""
        for name in ("vite.config.ts", "vite.config.js"):
            config = Path.cwd() / name
            if config.exists():
                content = config.read_text()
                if "@tailwindcss/vite" in content:
                    log_ok("Tailwind Vite plugin already configured.")
                    return

                # Add import and plugin
                if "tailwindcss" not in content:
                    new_import = "import tailwindcss from '@tailwindcss/vite';\n"
                    content = new_import + content

                    # Insert into plugins array
                    content = re.sub(
                        r"(plugins:\s*\[)",
                        r"\1\n    tailwindcss(),",
                        content,
                    )
                    config.write_text(content)
                    log_ok(f"Added Tailwind plugin to {name}")
                return
        log_info("No vite.config found — add @tailwindcss/vite plugin manually if using Vite.")

    # ══════════════════════════════════════════════════════════════════
    #  Combo setups
    # ══════════════════════════════════════════════════════════════════

    def _full_react_stack(self) -> None:
        """Node.js + React + Tailwind CSS."""
        if not self._ensure_node():
            return
        self._scaffold_react()

        # Tailwind inside the new project
        console.print()
        if confirm("Add Tailwind CSS to the project?"):
            # cd into project (check for recent scaffold)
            project_dirs = sorted(Path.cwd().iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            for d in project_dirs:
                if d.is_dir() and (d / "package.json").exists() and (d / "vite.config.ts").exists():
                    log_info(f"Adding Tailwind to {d.name}/")
                    self._add_tailwind_to_project(d)
                    break
            else:
                log_info("Scaffold your project first, then run 'Tailwind CSS' setup from inside it.")

    def _add_tailwind_to_project(self, project_dir: Path) -> None:
        """Install Tailwind CSS into a specific project directory."""
        npm = self._find_npm()
        if not npm:
            return

        try:
            run_cmd(
                [npm, "install", "tailwindcss", "@tailwindcss/vite"],
                check=True,
                capture=False,
            )
        except CommandError:
            log_err("Failed to install Tailwind packages.")
            return

        # Add import to CSS
        index_css = project_dir / "src" / "index.css"
        tw_import = '@import "tailwindcss";'
        if index_css.exists():
            content = index_css.read_text()
            if "tailwindcss" not in content:
                index_css.write_text(f"{tw_import}\n\n{content}")
        else:
            (project_dir / "src").mkdir(exist_ok=True)
            index_css.write_text(f"{tw_import}\n")

        # Patch vite config
        for name in ("vite.config.ts", "vite.config.js"):
            config = project_dir / name
            if config.exists():
                content = config.read_text()
                if "@tailwindcss/vite" not in content:
                    content = "import tailwindcss from '@tailwindcss/vite';\n" + content
                    content = re.sub(r"(plugins:\s*\[)", r"\1\n    tailwindcss(),", content)
                    config.write_text(content)
                break

        log_ok("Tailwind CSS added to project.")

    def _full_stack(self) -> None:
        """Complete web dev setup: Node + React + Tailwind + PHP + DB."""
        if not self._ensure_node():
            log_warn("Continuing without Node.js…")

        self._setup_php()

        console.print()
        if confirm("Scaffold a React project now?"):
            self._scaffold_react()

            console.print()
            if confirm("Add Tailwind CSS?"):
                project_dirs = sorted(
                    Path.cwd().iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
                )
                for d in project_dirs:
                    if d.is_dir() and (d / "package.json").exists():
                        self._add_tailwind_to_project(d)
                        break

        console.print()
        if confirm("Set up a database engine?"):
            self._database_menu()

        console.print()
        self._show_status()

    # ══════════════════════════════════════════════════════════════════
    #  Database Setup (delegates to DatabaseSetup)
    # ══════════════════════════════════════════════════════════════════

    def _database_menu(self) -> None:
        self.db.run()

    # ══════════════════════════════════════════════════════════════════
    #  Status overview
    # ══════════════════════════════════════════════════════════════════

    def _show_status(self) -> None:
        """Show a quick overview of installed web dev tools."""
        section("Web Development Environment Status")

        checks = [
            ("Node.js", shutil.which("node"), self._get_node_version() if shutil.which("node") else ""),
            ("npm", shutil.which("npm"), ""),
            ("npx", shutil.which("npx"), ""),
            ("PHP", shutil.which("php"), ""),
            ("Composer", shutil.which("composer"), ""),
            ("git", shutil.which("git"), ""),
        ]

        for name, path, ver in checks:
            icon = status_icon(bool(path))
            extra = f"  ({ver})" if ver else ""
            console.print(f"    {icon} {name}{extra}")

    # ══════════════════════════════════════════════════════════════════
    #  Helpers
    # ══════════════════════════════════════════════════════════════════

    def _find_npm(self) -> str | None:
        """Find npm, including nvm-managed versions."""
        npm = shutil.which("npm")
        if npm:
            return npm
        # Check nvm default
        nvm_npm = Path.home() / ".nvm" / "alias" / "default"
        if nvm_npm.exists():
            try:
                r = run_cmd(["bash", "-c", 'source ~/.nvm/nvm.sh && which npm'], check=False)
                path = (r.stdout or "").strip()
                if path:
                    return path
            except CommandError:
                pass
        return None

    def _find_npx(self) -> str | None:
        """Find npx, including nvm-managed versions."""
        npx = shutil.which("npx")
        if npx:
            return npx
        try:
            r = run_cmd(["bash", "-c", 'source ~/.nvm/nvm.sh && which npx'], check=False)
            path = (r.stdout or "").strip()
            if path:
                return path
        except CommandError:
            pass
        return None
