# ==============================================================================
# dev-setup.ps1 — One-time dependency installer for Windows
# Reads: generated\windows-requirements.json
# Installs to: C:\orthotech_dev\deps
#
# Usage (run PowerShell as Administrator):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\config\dev-setup.ps1 [OPTIONS]
#
# Options:
#   -Regen        Re-run generate_requirements.py before setup
#   -Clean        Wipe C:\orthotech_dev\deps and rebuild from scratch
#   -Build        Configure + build the project after deps are installed
#   -Test         Run tests after build (implies -Build)
#   -VcpkgCommit  vcpkg commit to pin (default: 2024.04.26)
#   -Help         Show this help
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
Header "Step 2 — vcpkg"
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
Ok "vcpkg ready."

# ── Step 4: vcpkg packages ────────────────────────────────────────────────────
Header "Step 3 — vcpkg packages"
# 🌟 FIXED: Using literal Here-String piped directly into python standard input
@'
import json, subprocess, sys, os
vcpkg_exe = os.path.join(os.environ['VCPKG_ROOT'], 'vcpkg.exe')
with open(r'C:\orthotech_dev\generated\windows-requirements.json') as f:
    data = json.load(f)
pkgs = data.get('vcpkg', [])
if not pkgs:
    print('  No vcpkg packages defined.')
    sys.exit(0)
for p in pkgs:
    name    = p['name']
    triplet = p.get('triplet', 'x64-windows')
    spec    = f'{name}:{triplet}'
    print(f'  Installing {spec}')
    r = subprocess.run([vcpkg_exe, 'install', spec])
    if r.returncode != 0:
        print(f'  [WARN] vcpkg install failed for {spec} — continuing.')
'@ | python -
if ($LASTEXITCODE -ne 0) { Err "vcpkg packages installation failed." }
Ok "vcpkg packages done."

# ── Step 5: pip packages ──────────────────────────────────────────────────────
Header "Step 4 — pip packages"
# 🌟 FIXED: Using literal Here-String piped directly into python standard input
@'
import json, subprocess, sys
with open(r'C:\orthotech_dev\generated\windows-requirements.json') as f:
    data = json.load(f)
pkgs = data.get('pip', [])
if not pkgs:
    print('  No pip packages defined.')
    sys.exit(0)
specs = [
    f"{p['name']}=={p['version']}" if p.get('version') and p['version'] != 'latest'
    else p['name']
    for p in pkgs
]
print(f"  Installing: {' '.join(specs)}")
subprocess.run([sys.executable, '-m', 'pip', 'install'] + specs, check=True)
'@ | python -
if ($LASTEXITCODE -ne 0) { Err "pip packages installation failed." }
Ok "pip packages done."

# ── Step 6: source builds ─────────────────────────────────────────────────────
Header "Step 5 — Source builds"
# 🌟 FIXED: Using literal Here-String piped directly into python standard input
@'
import json, os, subprocess, sys, shlex
from pathlib import Path

install_prefix = Path(r'C:\orthotech_dev\deps')
source_cache   = Path(r'C:\orthotech_dev\deps\src')

with open(r'C:\orthotech_dev\generated\windows-requirements.json') as f:
    data = json.load(f)

deps = data.get('source', [])
if not deps:
    print('  No source deps defined.')
    sys.exit(0)

cpu_count = str(os.cpu_count() or 4)

for dep in deps:
    name  = dep['name']
    tag   = dep['tag']
    stamp = source_cache / f'.{name}-{tag}.stamp'

    if stamp.exists():
        print(f'  [SKIP] {name}@{tag} already installed.')
        continue

    print(f'\n  [BUILD] {name}@{tag}')

    src_dir = source_cache / name
    if not src_dir.exists():
        subprocess.run([
            'git', 'clone', '--depth=1', '--branch', tag,
            dep['repo'], str(src_dir)
        ], check=True)

    build_root = src_dir / (dep.get('build_dir') or '')
    build_dir  = src_dir / '_build'
    build_dir.mkdir(exist_ok=True)

    cmake_extra = shlex.split(dep.get('cmake_args') or '')
    subprocess.run([
        'cmake', '-S', str(build_root), '-B', str(build_dir),
        '-DCMAKE_BUILD_TYPE=Release',
        f'-DCMAKE_INSTALL_PREFIX={install_prefix}',
    ] + cmake_extra, check=True)

    subprocess.run([
        'cmake', '--build', str(build_dir),
        '--config', 'Release',
        '--parallel', cpu_count
    ], check=True)

    subprocess.run([
        'cmake', '--install', str(build_dir), '--config', 'Release'
    ], check=True)

    post = dep.get('post_install', '').strip()
    if post:
        print(f'  [POST] {post}')
        subprocess.run(post, shell=True, check=True)

    stamp.touch()
    print(f'  [OK] {name} installed to {install_prefix}')

print(f'\n  All source deps installed to {install_prefix}')
'@ | python -
if ($LASTEXITCODE -ne 0) { Err "Source build failed." }
Ok "Source builds done."

# ── Step 7: optional project build ───────────────────────────────────────────
if ($Build) {
    Header "Step 6 — Build project"
    cmake --preset windows-release `
        "-DCMAKE_PREFIX_PATH=$InstallPrefix" `
        "-DCMAKE_TOOLCHAIN_FILE=$VcpkgDir\scripts\buildsystems\vcpkg.cmake"
    cmake --build $BuildDir --config Release --parallel 8
    if ($LASTEXITCODE -ne 0) { Err "Project build failed." }
    Ok "Project built."
}

# ── Step 8: optional tests ────────────────────────────────────────────────────
if ($Test) {
    Header "Step 7 — Tests"
    ctest --test-dir $BuildDir --build-config Release --output-on-failure --parallel 4
    if ($LASTEXITCODE -ne 0) { Err "Tests failed." }
    Ok "Tests passed."
}

# ── Done ──────────────────────────────────────────────────────────────────────
Header "Done"
Write-Host "  All dependencies installed to $InstallPrefix" -ForegroundColor Green
Write-Host ""
Write-Host "  CMake configure command if not using presets:" -ForegroundColor White
Write-Host "  cmake -S . -B build -DCMAKE_PREFIX_PATH=`"$InstallPrefix`" -DCMAKE_TOOLCHAIN_FILE=`"$VcpkgDir\scripts\buildsystems\vcpkg.cmake`"" -ForegroundColor Cyan
Write-Host ""