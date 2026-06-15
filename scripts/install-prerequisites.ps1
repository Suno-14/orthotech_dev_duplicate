# ==============================================================================
# install-prerequisites.ps1 — Install all build prerequisites on Windows 11
#
# Run this once on a fresh machine before anything else.
# Uses winget (built into Windows 11) — no third party tools needed.
#
# Usage (PowerShell as Administrator):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\install-prerequisites.ps1
# ==============================================================================

#Requires -RunAsAdministrator

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

function Install-WinGet($id, $name) {
    Log "Installing $name..."
    $result = winget list --id $id 2>$null
    if ($result -match $id) {
        Ok "$name already installed."
        return
    }
    winget install --id $id --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Warn "$name install may have failed. Check manually."
    } else {
        Ok "$name installed."
    }
}

function Check($name, $cmd, $ver) {
    try {
        $out = Invoke-Expression $cmd 2>$null | Select-Object -First 1
        Write-Host "  ✓ ${name}: $out" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ ${name}: NOT FOUND" -ForegroundColor Red
    }
}

# ── Banner ────────────────────────────────────────────────────────────────────
Clear-Host
Write-Host ""
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "   orthotech_dev — Windows Prerequisites Setup      " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host ""

# ── Winget check ──────────────────────────────────────────────────────────────
Header "Checking winget"
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Err "winget not found. Update Windows 11 or install App Installer from the Microsoft Store."
}
Ok "winget available."

# ── Step 0: PowerShell Core (pwsh) ──────────────────────────────────────
Header "Step 0 — PowerShell Core"
if (-not (Get-Command pwsh -ErrorAction SilentlyContinue)) {
    Install-WinGet "Microsoft.PowerShell" "PowerShell Core"
} else {
    Ok "PowerShell Core (pwsh) is already installed."
}

# ── Step 1: Git ───────────────────────────────────────────────────────────────
Header "Step 1 — Git"
Install-WinGet "Git.Git" "Git"

# Refresh PATH so git is available immediately
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("PATH","User")

# ── Step 2: CMake (3.22+) ─────────────────────────────────────────────────────
Header "Step 2 — CMake"
Install-WinGet "Kitware.CMake" "CMake"

# ── Step 3: Python 3.11 ───────────────────────────────────────────────────────
Header "Step 3 — Python 3.11"
Install-WinGet "Python.Python.3.11" "Python 3.11"

# ── Step 4: Visual Studio Build Tools 2022 ───────────────────────────────────
# Build Tools only — no full IDE (lighter, faster, perfect for build machines)
# Includes: MSVC compiler, Windows SDK, CMake integration
Header "Step 4 — Visual Studio Build Tools 2022"

$vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsInstalled = $false

if (Test-Path $vsWhere) {
    $vsVersion = & $vsWhere -latest -property installationVersion 2>$null
    if ($vsVersion -match "^17\.") {
        Ok "Visual Studio 2022 Build Tools already installed (v$vsVersion)."
        $vsInstalled = $true
    }
}

if (-not $vsInstalled) {
    Log "Installing Visual Studio Build Tools 2022..."
    Log "This is a large download (~3-4GB). Please wait..."

    $vsInstallerUrl = "https://aka.ms/vs/17/release/vs_BuildTools.exe"
    $vsInstaller    = "$env:TEMP\vs_BuildTools.exe"

    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -Uri $vsInstallerUrl -OutFile $vsInstaller
    $ProgressPreference = "Continue"

    # Install with C++ workload silently
    $vsArgs = @(
        "--quiet",
        "--wait",
        "--norestart",
        "--nocache",
        "--installPath", "C:\BuildTools",
        "--add", "Microsoft.VisualStudio.Workload.VCTools",          # C++ build tools
        "--add", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", # MSVC compiler
        "--add", "Microsoft.VisualStudio.Component.Windows11SDK.22621",# Windows SDK
        "--add", "Microsoft.VisualStudio.Component.CMake"             # CMake integration
    )

    Start-Process -FilePath $vsInstaller -ArgumentList $vsArgs -Wait -NoNewWindow

    if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq 3010) {
        Ok "Visual Studio Build Tools 2022 installed."
        if ($LASTEXITCODE -eq 3010) {
            Warn "A reboot is recommended to complete VS installation."
        }
    } else {
        Warn "VS Build Tools installer returned code $LASTEXITCODE. Verify manually."
    }
}

# ── Step 5: Ninja ─────────────────────────────────────────────────────────────
Header "Step 5 — Ninja"
Install-WinGet "Ninja-build.Ninja" "Ninja"

# ── Step 6: pip packages needed by the toolchain ─────────────────────────────
Header "Step 6 — Python toolchain packages"

# Refresh PATH to pick up newly installed Python
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("PATH","User")

python -m pip install --quiet --upgrade pip
python -m pip install --quiet pyyaml
Ok "pyyaml installed."

# ── Step 7: Verify ────────────────────────────────────────────────────────────
Header "Step 7 — Verification"

# Refresh PATH one more time before checks
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("PATH","User")

Check "git"    "git --version"               ">=2"
Check "cmake"  "cmake --version"             ">=3.22"
Check "python" "python --version"            ">=3.11"
Check "pip"    "python -m pip --version"     "any"
Check "ninja"  "ninja --version"             "any"

# Check MSVC via vswhere
if (Test-Path $vsWhere) {
    $vsPath = & $vsWhere -latest -property installationPath 2>$null
    Write-Host "  ✓ MSVC: found at $vsPath" -ForegroundColor Green
} else {
    Write-Host "  ✗ MSVC: not found — check VS Build Tools installation" -ForegroundColor Red
}

# ── Done ──────────────────────────────────────────────────────────────────────
Header "Done"
Write-Host "  All prerequisites installed." -ForegroundColor Green
Write-Host ""
Write-Host "  IMPORTANT: Close and reopen PowerShell as Administrator" -ForegroundColor Yellow
Write-Host "  so PATH changes take effect before running the next step." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Next step:" -ForegroundColor White
Write-Host "  .\dev-setup.ps1   <- install project dependencies" -ForegroundColor Cyan
Write-Host ""
