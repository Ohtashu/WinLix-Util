"""Web Development Setup Wizard — React, PHP, Tailwind CSS, Database engines.

Handles:
- Node.js (v24 LTS via nvm) + React project scaffolding
- PHP + Composer installation
- Tailwind CSS setup
- Database engines (MariaDB, MySQL, PostgreSQL, MongoDB)
- Cross-platform support (Linux + Windows basic)
"""

from __future__ import annotations

import os
import re
import shutil
import stat
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
    press_enter,
    status_icon,
)
from toolkit.util import CommandError, IS_LINUX, IS_WINDOWS, run_cmd, require_sudo

# ── Node.js target version ────────────────────────────────────────────

NODE_LTS_VERSION = "24"

# ── PHP package mappings ──────────────────────────────────────────────

_PHP_MAP: dict[str, str] = {
    "debian": "php php-cli php-mbstring php-xml php-curl php-zip php-mysql php-pgsql unzip",
    "fedora": "php php-cli php-mbstring php-xml php-curl php-zip php-mysqlnd php-pgsql unzip",
    "arch":   "php php-cgi php-gd php-intl unzip",
}

# ── Database package mappings ─────────────────────────────────────────

_DB_MAP: dict[str, dict[str, dict[str, str]]] = {
    "mariadb": {
        "debian": {"pkg": "mariadb-server mariadb-client", "svc": "mariadb"},
        "fedora": {"pkg": "mariadb-server", "svc": "mariadb"},
        "arch":   {"pkg": "mariadb", "svc": "mariadb"},
    },
    "mysql": {
        "debian": {"pkg": "mysql-server mysql-client", "svc": "mysql"},
        "fedora": {"pkg": "mysql-server", "svc": "mysqld"},
        "arch":   {"pkg": "mysql", "svc": "mysqld"},
    },
    "postgresql": {
        "debian": {"pkg": "postgresql postgresql-client", "svc": "postgresql"},
        "fedora": {"pkg": "postgresql-server postgresql", "svc": "postgresql"},
        "arch":   {"pkg": "postgresql", "svc": "postgresql"},
    },
    "mongodb": {
        "debian": {"pkg": "mongodb-org", "svc": "mongod"},
        "fedora": {"pkg": "mongodb-org", "svc": "mongod"},
        "arch":   {"pkg": "mongodb-bin", "svc": "mongodb"},
    },
}


class WebDevSetup:
    """Interactive web development environment setup wizard."""

    def __init__(self, system: SystemDetect, pkg: PackageManager) -> None:
        self.system = system
        self.pkg = pkg

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
    #  Database Setup (kept from original)
    # ══════════════════════════════════════════════════════════════════

    def _database_menu(self) -> None:
        section("Database Engine Setup")
        console.print("    [cyan]1)[/cyan] MariaDB")
        console.print("    [cyan]2)[/cyan] MySQL")
        console.print("    [cyan]3)[/cyan] PostgreSQL")
        console.print("    [cyan]4)[/cyan] MongoDB")
        console.print()
        console.print("    [dim]0)[/dim] Skip")
        console.print()

        from rich.prompt import Prompt
        choice = Prompt.ask("  Enter choice", default="0").strip()
        match choice:
            case "1": self._db_setup("mariadb")
            case "2": self._db_setup("mysql")
            case "3": self._db_setup("postgresql")
            case "4": self._db_setup("mongodb")
            case _:   return

    def _db_setup(self, engine: str) -> None:
        section(f"{engine.title()} Setup")

        family = self.system.distro_family
        info = _DB_MAP.get(engine, {}).get(family)
        if not info:
            log_err(f"No package mapping for {engine} on {family}.")
            return

        pkgs = info["pkg"]
        svc = info["svc"]
        log(f"Installing: {pkgs}")
        if not self.pkg.install(*pkgs.split()):
            log_err("Package installation failed.")
            return
        log_ok(f"{engine.title()} packages installed.")

        # PostgreSQL init on Arch/Fedora
        if engine == "postgresql":
            self._pg_init()

        # Enable + start service
        if IS_LINUX and shutil.which("systemctl"):
            try:
                require_sudo()
                run_cmd(["systemctl", "enable", "--now", svc], sudo=True, check=False)
                log_ok(f"Service '{svc}' enabled and started.")
            except Exception:
                log_warn(f"Could not enable service '{svc}'.")

        # Engine-specific config
        match engine:
            case "mariadb" | "mysql": self._mysql_wizard(engine)
            case "postgresql":        self._pg_wizard()
            case "mongodb":           self._mongo_wizard()

        # SQL file import
        if engine in ("mariadb", "mysql", "postgresql"):
            console.print()
            if confirm("Import a .sql file now?"):
                self._import_sql(engine)

        log_ok(f"{engine.title()} setup complete.")

    def _mysql_wizard(self, engine: str) -> None:
        section(f"{engine.title()} — Secure Configuration")

        secure_cmd = "mariadb-secure-installation" if engine == "mariadb" else "mysql_secure_installation"
        if shutil.which(secure_cmd):
            if confirm(f"Run {secure_cmd} (recommended)?"):
                log(f"Launching {secure_cmd}…")
                run_cmd([secure_cmd], sudo=True, capture=False, check=False)
                log_ok("Secure installation completed.")

        console.print()
        if not confirm("Create a new database user and database?"):
            return

        from rich.prompt import Prompt
        db_name = prompt("Database name")
        db_user = prompt("Username")
        db_pass = Prompt.ask("  Password", password=True)
        if not all((db_name, db_user, db_pass)):
            log_warn("All fields are required.")
            return

        client_cmd = "mariadb" if engine == "mariadb" and shutil.which("mariadb") else "mysql"
        sql = (
            f"CREATE DATABASE IF NOT EXISTS `{_safe_ident(db_name)}`;\n"
            f"CREATE USER IF NOT EXISTS '{_safe_ident(db_user)}'@'localhost' IDENTIFIED BY '{_safe_str(db_pass)}';\n"
            f"GRANT ALL PRIVILEGES ON `{_safe_ident(db_name)}`.* TO '{_safe_ident(db_user)}'@'localhost';\n"
            f"FLUSH PRIVILEGES;\n"
        )
        self._exec_sql_via_tempfile(client_cmd, sql, sudo=True)

    def _pg_init(self) -> None:
        """Initialize PostgreSQL data directory on Arch / Fedora if needed."""
        data_dir = Path("/var/lib/postgres/data")
        if self.system.distro_family == "fedora":
            data_dir = Path("/var/lib/pgsql/data")
            if not (data_dir / "PG_VERSION").exists():
                log("Initializing PostgreSQL database cluster…")
                run_cmd(["postgresql-setup", "--initdb"], sudo=True, check=False)
        elif self.system.distro_family == "arch":
            if not (data_dir / "PG_VERSION").exists():
                log("Initializing PostgreSQL database cluster…")
                run_cmd(["mkdir", "-p", str(data_dir)], sudo=True, check=False)
                run_cmd(["chown", "postgres:postgres", str(data_dir)], sudo=True, check=False)
                run_cmd(
                    ["sudo", "-u", "postgres", "initdb", "-D", str(data_dir)],
                    sudo=False,
                    check=False,
                )
                log_ok("PostgreSQL cluster initialized.")

    def _pg_wizard(self) -> None:
        section("PostgreSQL — User & Database Setup")
        console.print()
        if not confirm("Create a new PostgreSQL user and database?"):
            return

        from rich.prompt import Prompt
        db_name = prompt("Database name")
        db_user = prompt("Username")
        db_pass = Prompt.ask("  Password", password=True)
        if not all((db_name, db_user, db_pass)):
            log_warn("All fields are required.")
            return

        sql_user = (
            f"DO $$ BEGIN\n"
            f"  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{_safe_ident(db_user)}') THEN\n"
            f"    CREATE ROLE \"{_safe_ident(db_user)}\" WITH LOGIN PASSWORD '{_safe_str(db_pass)}';\n"
            f"  END IF;\n"
            f"END $$;\n"
        )
        sql_db = (
            f"SELECT 'CREATE DATABASE \"{_safe_ident(db_name)}\" OWNER \"{_safe_ident(db_user)}\"'\n"
            f"WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{_safe_ident(db_name)}')\\gexec\n"
        )
        self._exec_pg_sql(sql_user + sql_db)

    def _exec_pg_sql(self, sql: str) -> None:
        fd, tmp_path = tempfile.mkstemp(suffix=".sql", prefix="pgsetup_")
        try:
            os.write(fd, sql.encode())
            os.close(fd)
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
            run_cmd(
                ["sudo", "-u", "postgres", "psql", "-f", tmp_path],
                check=False,
            )
            log_ok("PostgreSQL commands executed.")
        except CommandError as e:
            log_err(f"psql error: {e.stderr}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _mongo_wizard(self) -> None:
        section("MongoDB — Initial Configuration")
        if not shutil.which("mongosh") and not shutil.which("mongo"):
            log_info("mongosh not found. Install it to manage MongoDB interactively.")
            return

        console.print()
        if not confirm("Create an admin user for MongoDB?"):
            return

        from rich.prompt import Prompt
        admin_user = prompt("Admin username")
        admin_pass = Prompt.ask("  Admin password", password=True)
        if not all((admin_user, admin_pass)):
            log_warn("Both username and password are required.")
            return

        shell_cmd = "mongosh" if shutil.which("mongosh") else "mongo"
        js = (
            f"db = db.getSiblingDB('admin');\n"
            f"db.createUser({{\n"
            f"  user: '{_safe_str(admin_user)}',\n"
            f"  pwd: '{_safe_str(admin_pass)}',\n"
            f"  roles: [{{ role: 'root', db: 'admin' }}]\n"
            f"}});\n"
        )
        fd, tmp_path = tempfile.mkstemp(suffix=".js", prefix="mongosetup_")
        try:
            os.write(fd, js.encode())
            os.close(fd)
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
            run_cmd([shell_cmd, "--quiet", tmp_path], check=False)
            log_ok("MongoDB admin user created.")
            log_info("Enable auth in /etc/mongod.conf: security.authorization: enabled")
        except CommandError as e:
            log_err(f"MongoDB shell error: {e.stderr}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _import_sql(self, engine: str) -> None:
        section("Import SQL File")
        file_path = prompt("Path to .sql file")
        if not file_path:
            return
        sql_file = Path(file_path).expanduser()
        if not sql_file.is_file():
            log_err(f"File not found: {sql_file}")
            return

        db_name = prompt("Target database name")
        if not db_name:
            return

        if engine in ("mariadb", "mysql"):
            client = "mariadb" if engine == "mariadb" and shutil.which("mariadb") else "mysql"
            from rich.prompt import Prompt
            user = prompt("MySQL/MariaDB username", default="root")
            passwd = Prompt.ask("  Password", password=True, default="")
            cmd = [client, "-u", user, _safe_ident(db_name)]
            if passwd:
                cmd.extend([f"--password={passwd}"])
            log(f"Importing {sql_file.name} into {db_name}…")
            try:
                with sql_file.open("r") as f:
                    run_cmd(cmd, check=True, input_text=f.read())
                log_ok(f"SQL file imported into '{db_name}'.")
            except CommandError as e:
                log_err(f"Import failed: {e.stderr}")
        elif engine == "postgresql":
            log(f"Importing {sql_file.name} into {db_name}…")
            try:
                run_cmd(
                    ["sudo", "-u", "postgres", "psql", "-d", _safe_ident(db_name), "-f", str(sql_file)],
                    check=False,
                )
                log_ok(f"SQL file imported into '{db_name}'.")
            except CommandError as e:
                log_err(f"Import failed: {e.stderr}")

    def _exec_sql_via_tempfile(self, client: str, sql: str, *, sudo: bool = False) -> None:
        fd, tmp_path = tempfile.mkstemp(suffix=".sql", prefix="dbsetup_")
        try:
            os.write(fd, sql.encode())
            os.close(fd)
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
            with open(tmp_path, "r") as f:
                run_cmd([client], sudo=sudo, input_text=f.read(), check=False)
            log_ok("Database commands executed.")
        except CommandError as e:
            log_err(f"SQL error: {e.stderr}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

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


def _safe_ident(s: str) -> str:
    """Sanitize a SQL identifier — allow only alphanumeric and underscore."""
    return re.sub(r"[^a-zA-Z0-9_]", "", s)


def _safe_str(s: str) -> str:
    """Escape single quotes for SQL string literals (standard SQL doubling)."""
    return s.replace("'", "''")
