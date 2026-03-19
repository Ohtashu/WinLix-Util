# ─────────────────────────────────────────────────────────
#  WinLix-Util — run without cloning (Windows PowerShell)
#
#  Usage:
#    irm https://raw.githubusercontent.com/Ohtashu/WinLix-Util/main/install.ps1 | iex
# ─────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

$Repo       = "Ohtashu/WinLix-Util"
$Branch     = "main"
$InstallDir = if ($env:WINLIX_INSTALL_DIR) { $env:WINLIX_INSTALL_DIR } else { "$env:USERPROFILE\.winlix-util" }

Write-Host "──────────────────────────────────────────"
Write-Host "  WinLix-Util  —  remote launcher"
Write-Host "──────────────────────────────────────────"

# ── Ensure python is available ───────────────────────────
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "python not found. Install Python 3.10+ from https://python.org"
    exit 1
}

# ── Download / update ────────────────────────────────────
if (-not (Test-Path "$InstallDir\pyproject.toml")) {
    Write-Host "Downloading WinLix-Util…"
    $ZipUrl  = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"
    $ZipPath = "$env:TEMP\winlix-util.zip"
    $ExtractPath = "$env:TEMP\winlix-extract"

    Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath -UseBasicParsing
    if (Test-Path $ExtractPath) { Remove-Item $ExtractPath -Recurse -Force }
    Expand-Archive -Path $ZipPath -DestinationPath $ExtractPath

    $Inner = Get-ChildItem $ExtractPath | Select-Object -First 1
    if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
    Move-Item $Inner.FullName $InstallDir

    Remove-Item $ZipPath -Force
    Remove-Item $ExtractPath -Recurse -Force
} else {
    Write-Host "WinLix-Util already installed at $InstallDir"
    Write-Host "  To update: Remove-Item '$InstallDir' -Recurse -Force  and re-run."
}

# ── Create venv if missing ───────────────────────────────
$VenvDir = "$InstallDir\.venv"
if (-not (Test-Path "$VenvDir\Scripts\python.exe")) {
    Write-Host "Creating virtual environment…"
    python -m venv $VenvDir
}

# ── Install deps if needed ───────────────────────────────
$ErrorActionPreference = "Continue"
& "$VenvDir\Scripts\python.exe" -c "import toolkit" 2>$null
$NeedInstall = $LASTEXITCODE -ne 0
$ErrorActionPreference = "Stop"
if ($NeedInstall) {
    Write-Host "Installing dependencies…"
    & "$VenvDir\Scripts\pip.exe" install --upgrade pip -q
    & "$VenvDir\Scripts\pip.exe" install -e $InstallDir -q
}

# ── Launch ───────────────────────────────────────────────
Write-Host ""
& "$VenvDir\Scripts\python.exe" -m toolkit @args
