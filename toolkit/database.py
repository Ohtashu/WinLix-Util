"""Interactive database setup wizard — MariaDB, MySQL, PostgreSQL, MongoDB.

Handles:
- Package installation via PackageManager
- Service enable/start
- Secure initial configuration (password prompts, user/db creation)
- SQL file import
- Cross-platform support (Linux + Windows basic)
"""

from __future__ import annotations

import os
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
    menu_table,
    press_enter,
)
from toolkit.util import CommandError, IS_LINUX, run_cmd, require_sudo

# ── Package mappings ──────────────────────────────────────────────────

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


class DatabaseSetup:
    """Interactive database server setup wizard."""

    def __init__(self, system: SystemDetect, pkg: PackageManager) -> None:
        self.system = system
        self.pkg = pkg

    def run(self) -> None:
        banner("Database Setup Wizard")
        console.print("  Select a database engine to install and configure:")
        console.print()
        console.print("    [cyan]1)[/cyan] MariaDB")
        console.print("    [cyan]2)[/cyan] MySQL")
        console.print("    [cyan]3)[/cyan] PostgreSQL")
        console.print("    [cyan]4)[/cyan] MongoDB")
        console.print()
        console.print("    [dim]0)[/dim] Cancel")
        console.print()

        from rich.prompt import Prompt
        choice = Prompt.ask("  Enter choice", default="0").strip()
        match choice:
            case "1": self._setup("mariadb")
            case "2": self._setup("mysql")
            case "3": self._setup("postgresql")
            case "4": self._setup("mongodb")
            case _:   return

    # ── Generic setup flow ────────────────────────────────────────────

    def _setup(self, engine: str) -> None:
        section(f"{engine.title()} Setup")

        family = self.system.distro_family
        info = _DB_MAP.get(engine, {}).get(family)
        if not info:
            log_err(f"No package mapping for {engine} on {family}.")
            return

        # Install
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

        # Engine-specific config wizard
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

    # ── MySQL / MariaDB wizard ────────────────────────────────────────

    def _mysql_wizard(self, engine: str) -> None:
        section(f"{engine.title()} — Secure Configuration")

        # Run mysql_secure_installation if available
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

        # Build SQL commands
        client_cmd = "mariadb" if engine == "mariadb" and shutil.which("mariadb") else "mysql"
        sql = (
            f"CREATE DATABASE IF NOT EXISTS `{_safe_ident(db_name)}`;\n"
            f"CREATE USER IF NOT EXISTS '{_safe_ident(db_user)}'@'localhost' IDENTIFIED BY '{_safe_str(db_pass)}';\n"
            f"GRANT ALL PRIVILEGES ON `{_safe_ident(db_name)}`.* TO '{_safe_ident(db_user)}'@'localhost';\n"
            f"FLUSH PRIVILEGES;\n"
        )

        self._exec_sql_via_tempfile(client_cmd, sql, sudo=True)

    # ── PostgreSQL wizard ─────────────────────────────────────────────

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
        """Execute SQL as the postgres system user via psql."""
        fd, tmp_path = tempfile.mkstemp(suffix=".sql", prefix="pgsetup_")
        try:
            os.write(fd, sql.encode())
            os.close(fd)
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600

            run_cmd(
                ["sudo", "-u", "postgres", "psql", "-f", tmp_path],
                check=False,
            )
            log_ok("PostgreSQL commands executed.")
        except CommandError as e:
            log_err(f"psql error: {e.stderr}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # ── MongoDB wizard ────────────────────────────────────────────────

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

    # ── SQL import ────────────────────────────────────────────────────

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

    # ── Helpers ───────────────────────────────────────────────────────

    def _exec_sql_via_tempfile(self, client: str, sql: str, *, sudo: bool = False) -> None:
        """Write SQL to a temp file with restricted perms, execute, then delete."""
        fd, tmp_path = tempfile.mkstemp(suffix=".sql", prefix="dbsetup_")
        try:
            os.write(fd, sql.encode())
            os.close(fd)
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600

            with open(tmp_path, "r") as f:
                run_cmd([client], sudo=sudo, input_text=f.read(), check=False)
            log_ok("Database commands executed.")
        except CommandError as e:
            log_err(f"SQL error: {e.stderr}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)


def _safe_ident(s: str) -> str:
    """Sanitize a SQL identifier — allow only alphanumeric and underscore."""
    import re
    return re.sub(r"[^a-zA-Z0-9_]", "", s)


def _safe_str(s: str) -> str:
    """Escape single quotes for SQL string literals (standard SQL doubling)."""
    return s.replace("'", "''")
