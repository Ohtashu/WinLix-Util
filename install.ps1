# ─────────────────────────────────────────────────────────
#  WinLix-Util — run without cloning (Windows PowerShell)
#
#  Usage (from any PowerShell, even with restricted policy):
#    powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/Ohtashu/WinLix-Util/main/install.ps1 | iex"
#
#  Or simply (if policy allows):
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

# ── Check for Administrator privileges ───────────────────
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $IsAdmin) {
    Write-Host "  Note: Running without Administrator privileges." -ForegroundColor Yellow
    Write-Host "  Some toolkit features (e.g. winget, registry) may require elevation." -ForegroundColor Yellow
    Write-Host "  To self-elevate, run:" -ForegroundColor Yellow
    Write-Host "    Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -Command ""irm https://raw.githubusercontent.com/Ohtashu/WinLix-Util/main/install.ps1 | iex""'" -ForegroundColor Cyan
    Write-Host ""
}

# ── Find Python: try python, py launcher, python3 ────────
$PythonCmd = $null
foreach ($candidate in @("python", "py", "python3")) {
    $found = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($found) {
        # Verify it's real Python, not the Windows Store stub
        $testOutput = & $candidate -c "import sys; print(sys.version_info[:2])" 2>&1
        if ($LASTEXITCODE -eq 0 -and $testOutput -match "\(3,") {
            $PythonCmd = $candidate
            break
        }
    }
}

if (-not $PythonCmd) {
    Write-Host "ERROR: Python 3.10+ not found." -ForegroundColor Red
    Write-Host "  Install from https://python.org (ensure 'Add to PATH' is checked)" -ForegroundColor Yellow
    Write-Host "  Or install via: winget install Python.Python.3.12" -ForegroundColor Yellow
    exit 1
}

# Verify version >= 3.10
$PyVer = & $PythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
$PyMajor = & $PythonCmd -c "import sys; print(sys.version_info.major)" 2>&1
$PyMinor = & $PythonCmd -c "import sys; print(sys.version_info.minor)" 2>&1
if ([int]$PyMajor -lt 3 -or ([int]$PyMajor -eq 3 -and [int]$PyMinor -lt 10)) {
    Write-Host "ERROR: Python 3.10+ required (found $PyVer)." -ForegroundColor Red
    exit 1
}
Write-Host "  Python: $PythonCmd ($PyVer)"

# ── Download source if not present ───────────────────────
if (-not (Test-Path "$InstallDir\pyproject.toml")) {
    Write-Host "  Downloading WinLix-Util…"
    $ZipUrl      = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"
    $ZipPath     = "$env:TEMP\winlix-util.zip"
    $ExtractPath = "$env:TEMP\winlix-extract"

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath -UseBasicParsing
    } catch {
        Write-Host "ERROR: Failed to download — check your internet connection." -ForegroundColor Red
        Write-Host "  $_" -ForegroundColor DarkGray
        exit 1
    }

    if (Test-Path $ExtractPath) { Remove-Item $ExtractPath -Recurse -Force }
    Expand-Archive -Path $ZipPath -DestinationPath $ExtractPath

    $Inner = Get-ChildItem $ExtractPath | Select-Object -First 1
    if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
    Move-Item $Inner.FullName $InstallDir

    Remove-Item $ZipPath -Force
    Remove-Item $ExtractPath -Recurse -Force
    Write-Host "  ✔ Source downloaded."
} else {
    Write-Host "  Source found at $InstallDir"
}

# ── Create venv if missing or broken ─────────────────────
if (-not (Test-Path $VenvPython)) {
    Write-Host "  Creating virtual environment…"
    & $PythonCmd -m venv "$VenvDir" 2>&1 | Out-Null
    if (-not (Test-Path $VenvPython)) {
        Write-Host "ERROR: Failed to create virtual environment." -ForegroundColor Red
        Write-Host "  Ensure 'python -m venv' works on your system." -ForegroundColor Yellow
        exit 1
    }
}

# ── Install toolkit if not yet installed ─────────────────
& $VenvPython -c "import toolkit" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Installing dependencies…"
    & $VenvPython -m pip install --upgrade pip -q 2>&1 | Out-Null
    & $VenvPython -m pip install -e "$InstallDir" -q 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: pip install failed." -ForegroundColor Red
        Write-Host "  Try manually: & '$VenvPython' -m pip install -e '$InstallDir'" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  ✔ Dependencies installed."
}

# ── Create a global wrapper batch file ────────────────────
$BinDir = "$env:USERPROFILE\.local\bin"
if (-not (Test-Path $BinDir)) { New-Item -ItemType Directory -Path $BinDir -Force | Out-Null }
$WrapperBat = "$BinDir\winlix-util.bat"
$WrapperContent = "@echo off`r`n`"$VenvPython`" -m toolkit %*"
[System.IO.File]::WriteAllText($WrapperBat, $WrapperContent)

# Check if BinDir is on PATH
if ($env:PATH -notlike "*$BinDir*") {
    Write-Host ""
    Write-Host "  ℹ  To run from anywhere, add to your PATH:" -ForegroundColor Cyan
    Write-Host "      `$env:PATH += `";$BinDir`"" -ForegroundColor Cyan
    Write-Host "      Or permanently:" -ForegroundColor DarkGray
    Write-Host "      [Environment]::SetEnvironmentVariable('PATH', `$env:PATH + ';$BinDir', 'User')" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  ✔ WinLix-Util installed." -ForegroundColor Green

# ── Launch ───────────────────────────────────────────────
Write-Host ""
& $VenvPython -m toolkit
