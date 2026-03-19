# ─────────────────────────────────────────────────────────
#  WinLix-Util — run without cloning (Windows PowerShell)
#
#  Usage:
#    irm https://raw.githubusercontent.com/Ohtashu/WinLix-Util/main/install.ps1 | iex
# ─────────────────────────────────────────────────────────

# Use "Continue" globally — native commands (python, pip) write to stderr
# for warnings/notices, and "Stop" would turn those into terminating errors.
$ErrorActionPreference = "Continue"

$Repo       = "Ohtashu/WinLix-Util"
$Branch     = "main"
$InstallDir = if ($env:WINLIX_INSTALL_DIR) { $env:WINLIX_INSTALL_DIR } else { "$env:USERPROFILE\.winlix-util" }
$VenvDir    = "$InstallDir\.venv"
$VenvPython = "$VenvDir\Scripts\python.exe"
$VenvPip    = "$VenvDir\Scripts\pip.exe"

Write-Host "──────────────────────────────────────────"
Write-Host "  WinLix-Util  —  remote launcher"
Write-Host "──────────────────────────────────────────"

# ── Ensure python is available ───────────────────────────
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: python not found. Install Python 3.10+ from https://python.org" -ForegroundColor Red
    exit 1
}

# ── Download source if not present ───────────────────────
if (-not (Test-Path "$InstallDir\pyproject.toml")) {
    Write-Host "Downloading WinLix-Util…"
    $ZipUrl      = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"
    $ZipPath     = "$env:TEMP\winlix-util.zip"
    $ExtractPath = "$env:TEMP\winlix-extract"

    try {
        Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath -UseBasicParsing
    } catch {
        Write-Host "ERROR: Failed to download — check your internet connection." -ForegroundColor Red
        exit 1
    }

    if (Test-Path $ExtractPath) { Remove-Item $ExtractPath -Recurse -Force }
    Expand-Archive -Path $ZipPath -DestinationPath $ExtractPath

    $Inner = Get-ChildItem $ExtractPath | Select-Object -First 1
    if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
    Move-Item $Inner.FullName $InstallDir

    Remove-Item $ZipPath -Force
    Remove-Item $ExtractPath -Recurse -Force
} else {
    Write-Host "Source found at $InstallDir"
}

# ── Create venv if missing or broken ─────────────────────
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment…"
    python -m venv "$VenvDir" 2>&1 | Out-Null
    if (-not (Test-Path $VenvPython)) {
        Write-Host "ERROR: Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
}

# ── Install toolkit if not yet installed ─────────────────
& $VenvPython -c "import toolkit" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies…"
    & $VenvPip install --upgrade pip -q 2>&1 | Out-Null
    & $VenvPip install -e "$InstallDir" -q 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: pip install failed." -ForegroundColor Red
        exit 1
    }
}

# ── Launch ───────────────────────────────────────────────
Write-Host ""
& $VenvPython -m toolkit
