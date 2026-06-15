# ==============================================================================
# dev-setup.ps1 — One-time dependency installer for Windows
# ==============================================================================
param(
    [switch]$Regen,
    [switch]$Clean,
    [switch]$Build,
    [switch]$Test,
    [string]$VcpkgCommit = "2024.04.26",
    [switch]$Help
)

if ($Help) {
    Get-Content $MyInvocation.MyCommand.Path |
        Where-Object { $_ -match "^#" -and $_ -notmatch "^#!" } |
        ForEach-Object { $_ -replace "^# ?","" }
    exit 0
}

if ($Test) { $Build = $true }

# ── Helpers ───────────────────────────────────────────────────────────────────
function Header($msg) {
    Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
}
function Log($msg)  { Write-Host "[INFO]   $msg" -ForegroundColor Gray }
function Ok($msg)   { Write-Host "[OK]     $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[WARN]   $msg" -ForegroundColor Yellow }
function Err($msg)  { Write-Host "[ERROR]  $msg" -ForegroundColor Red; exit 1 }

function Require($cmd) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Err "'$cmd' not found in PATH. Please install it first."
    }
}

# ── Paths ─────────────────────────────────────────────────────────────────────
$ScriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot      = Split-Path -Parent $ScriptDir
$ReqFile       = Join-Path $RepoRoot "generated\windows-requirements.json"
$InstallPrefix = "C:\orthotech_dev\deps"
$SourceCache   = Join-Path $InstallPrefix "src"
$VcpkgDir      = "C:\orthotech_dev\vcpkg"
$BuildDir      = Join-Path $RepoRoot "build"

# ── Sanity checks ─────────────────────────────────────────────────────────────
Header "orthotech_dev — Windows Dev Setup"
Require "python"
Require "git"
Require "cmake"

Log "Repo root      : $RepoRoot"
Log "Install prefix : $InstallPrefix"
Log "vcpkg dir      : $VcpkgDir"
Log "Requirements   : $ReqFile"

# ── Step 1: Regen ─────────────────────────────────────────────────────────────
Header "Step 1 — Requirements"
if ($Regen -or -not (Test-Path $ReqFile)) {
    python -m pip install --quiet pyyaml
    python "$ScriptDir\generate_requirements.py" --validate
    Ok "Requirements generated."
} else {
    Log "windows-requirements.json exists. Use -Regen to regenerate."
}

# ── Step 2: Clean ─────────────────────────────────────────────────────────────
if ($Clean -and (Test-Path $InstallPrefix)) {
    Warn "-Clean: removing $InstallPrefix"
    Remove-Item -Recurse -Force $InstallPrefix
}
New-Item -ItemType Directory -Force -Path $InstallPrefix | Out-Null
New-Item -ItemType Directory -Force -Path $SourceCache   | Out-Null

# ── Step 3: Bootstrap vcpkg ───────────────────────────────────────────────────
Header "Step 2 — Bootstrap vcpkg"
if (-not (Test-Path $VcpkgDir)) {
    Log "Cloning vcpkg..."
    git clone https://github.com/microsoft/vcpkg.git $VcpkgDir
}
Push-Location $VcpkgDir
    git fetch --depth=1 origin $VcpkgCommit 2>$null
    git checkout $VcpkgCommit
    if (-not (Test-Path "$VcpkgDir\vcpkg.exe")) {
        & "$VcpkgDir\bootstrap-vcpkg.bat" -disableMetrics
    }
Pop-Location
$env:VCPKG_ROOT = $VcpkgDir
Ok "vcpkg bootstrapped successfully."

# ── Step 4: Core Python Package Orchestrator Pass ─────────────────────────────
Header -msg "Step 3 - Run Dependency Installations for vcpkg and pip and source"
# Invoke your isolated Python dependency installer file directly
python "$ScriptDir\install_requirements_windows.py"
if ($LASTEXITCODE -ne 0) { Err "Package orchestration failed inside Python routine." }
Ok "Dependencies fully resolved."


# ── Step 5: optional project build ───────────────────────────────────────────
if ($Build) {
    Header "Step 4 — Build project"
    cmake --preset windows-release `
        "-DCMAKE_PREFIX_PATH=$InstallPrefix" `
        "-DCMAKE_TOOLCHAIN_FILE=$VcpkgDir\scripts\buildsystems\vcpkg.cmake"
    cmake --build $BuildDir --config Release --parallel 8
    if ($LASTEXITCODE -ne 0) { Err "Project build failed." }
    Ok "Project built."
}

# ── Step 6: optional tests ────────────────────────────────────────────────────
if ($Test) {
    Header "Step 5 — Tests"
    ctest --test-dir $BuildDir --build-config Release --output-on-failure --parallel 4
    if ($LASTEXITCODE -ne 0) { Err "Tests failed." }
    Ok "Tests passed."
}

# ── Done ──────────────────────────────────────────────────────────────────────
Header "Done"
Write-Host "  All dependencies installed to $InstallPrefix" -ForegroundColor Green