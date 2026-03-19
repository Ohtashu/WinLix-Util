# WinLix-Util

Cross-platform system provisioning & automation CLI — one toolkit for Linux (Arch, Fedora, Debian) and Windows.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Quick Start

### Run without cloning

**Linux / macOS:**

```bash
curl -fsSL https://raw.githubusercontent.com/Ohtashu/WinLix-Util/main/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/Ohtashu/WinLix-Util/main/install.ps1 | iex
```

### Run locally

```bash
git clone https://github.com/Ohtashu/WinLix-Util.git
cd WinLix-Util
./run.sh        # Linux / macOS
# run.bat       # Windows
```

## Features

| Module | Platform | Description |
|--------|----------|-------------|
| **DE / WM Switcher** | Linux | Install and switch between GNOME, KDE, XFCE, MATE, Budgie, Hyprland, Sway with safe removal of old DE packages |
| **System Maintenance** | Linux | Disk health (TRIM, SMART), broken package repair, driver & firmware diagnostics |
| **Hardware Optimization** | Linux | Laptop (TLP, auto-cpufreq) and desktop (GameMode, CPU governor) tuning via chassis detection |
| **Developer Tools** | All | Git, GCC, Node.js, ripgrep, fd + LazyVim / Neovim setup |
| **Theming Engine** | All | KDE global themes, SDDM login screens, WM dotfiles, Firefox WhiteSur theme, macOS-style one-click setup |
| **Web Dev Setup** | All | Node.js (nvm), React scaffolding, PHP + Composer, Tailwind CSS, MariaDB / MySQL / PostgreSQL / MongoDB |

## Supported Platforms

| Platform | Package Manager |
|----------|----------------|
| Arch Linux | pacman + AUR (yay/paru) |
| Fedora | dnf |
| Debian / Ubuntu | apt |
| Windows | winget / chocolatey |

## Requirements

- Python 3.10+
- That's it — the launcher scripts handle the rest (venv, dependencies).

## Project Structure

```
toolkit/
├── app.py            # Main entry point & menu
├── detection.py      # OS / distro / DE / chassis detection
├── packages.py       # Package manager abstraction
├── database.py       # Database setup wizards
├── dev_tools.py      # Developer tools installer
├── de_switcher.py    # Desktop environment switcher
├── hardware.py       # Hardware optimization
├── maintenance.py    # System health & repair
├── webdev.py         # Web development setup
├── ui.py             # Rich terminal UI
├── util.py           # Shared utilities
└── theming/
    ├── base.py       # Theme router
    ├── kde.py        # KDE global themes
    ├── sddm.py       # SDDM login screen themes
    ├── firefox.py    # Firefox theming
    ├── windows.py    # Windows theming
    └── wm_dotfiles.py # Hyprland / Sway dotfiles
```
