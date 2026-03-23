"""Rich-based terminal UI — console singleton, logging helpers,
and table builders used throughout the toolkit.
"""

from __future__ import annotations

import logging
import tempfile
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# ── Logging to file ──────────────────────────────────────────────────────

_LOG_DIR = Path(tempfile.gettempdir())
LOG_FILE = _LOG_DIR / "linux-toolkit.log"

_file_logger = logging.getLogger("toolkit.file")
_file_logger.setLevel(logging.DEBUG)
_fh = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
_fh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
_file_logger.addHandler(_fh)

# ── Rich console singleton ───────────────────────────────────────────────

_THEME = Theme(
    {
        "ok": "bold green",
        "warn": "bold yellow",
        "err": "bold red",
        "info": "bold cyan",
        "dim": "dim",
        "accent": "bold magenta",
        "banner_border": "bold blue",
        "banner_title": "bold cyan",
    }
)

console = Console(theme=_THEME, highlight=False)
_stderr_console = Console(theme=_THEME, highlight=False, stderr=True)

# ── Timestamp helper ─────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ── Logging helpers (console + file) ─────────────────────────────────────

def log(msg: str) -> None:
    console.print(f"[dim]\\[{_ts()}][/dim] {msg}")
    _file_logger.info(msg)


def log_ok(msg: str) -> None:
    console.print(f"  [ok]✔ {msg}[/ok]")
    _file_logger.info("OK: %s", msg)


def log_warn(msg: str) -> None:
    console.print(f"  [warn]⚠ {msg}[/warn]")
    _file_logger.warning(msg)


def log_err(msg: str) -> None:
    _stderr_console.print(f"  [err]✖ {msg}[/err]")
    _file_logger.error(msg)


def log_info(msg: str) -> None:
    console.print(f"  [info]ℹ {msg}[/info]")
    _file_logger.info(msg)

# ── Pretty-print helpers ─────────────────────────────────────────────────

def banner(title: str, *, subtitle: str = "") -> None:
    console.print()
    body = Text(title, style="banner_title", justify="center")
    if subtitle:
        body.append(f"\n{subtitle}", style="dim")
    console.print(
        Panel(body, border_style="banner_border", padding=(1, 4))
    )
    console.print()


def section(title: str) -> None:
    console.print()
    console.print(f"[accent]── {title} ──[/accent]")
    console.print()


def separator() -> None:
    console.print("[dim]" + "─" * 60 + "[/dim]")


def press_enter() -> None:
    console.print()
    Prompt.ask("  Press Enter to return to the menu", default="")


def confirm(question: str) -> bool:
    return Confirm.ask(f"  [warn]➜[/warn] {question}", default=False)


def prompt(label: str, *, default: str = "", password: bool = False) -> str:
    return Prompt.ask(f"  {label}", default=default or None, password=password) or ""


def prompt_choice(label: str, choices: list[str]) -> str:
    return Prompt.ask(f"  {label}", choices=choices)

# ── Table builder shortcuts ──────────────────────────────────────────────

def info_table(title: str, rows: list[tuple[str, str]]) -> None:
    table = Table(title=title, show_header=False, border_style="blue", padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")
    for key, value in rows:
        table.add_row(key, value)
    console.print(table)
    console.print()


def menu_table(items: list[tuple[str, str]]) -> None:
    """Display a simple numbered menu from (key, label) pairs."""
    console.print()
    for key, label in items:
        if key == "0":
            console.print(f"    [dim]{key})[/dim] {label}")
        else:
            console.print(f"    [cyan]{key})[/cyan] {label}")
    console.print()


def status_icon(ok: bool) -> str:
    return "[ok]✔[/ok]" if ok else "[err]✖[/err]"
