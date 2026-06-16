#!/usr/bin/env bash
# ==============================================================================
# install-prerequisites.sh — Install all build prerequisites on Linux
# ==============================================================================

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()    { echo -e "${CYAN}[INFO]${RESET}   $*"; }
ok()     { echo -e "${GREEN}[OK]${RESET}     $*"; }
warn()   { echo -e "${YELLOW}[WARN]${RESET}   $*"; }
err()    { echo -e "${RED}[ERROR]${RESET}  $*" >&2; exit 1; }
header() {
    echo -e "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${BOLD}  $*${RESET}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
}

# ── Root check ────────────────────────────────────────────────────────────────
if [[ "$EUID" -eq 0 ]]; then
    err "Do not run as root. Run as your normal user — sudo will be used where needed."
fi

command -v sudo &>/dev/null || err "sudo not found. Please install it first."

# ── Banner ────────────────────────────────────────────────────────────────────
clear
echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║     orthotech_dev — Linux Prerequisites Setup        ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"

# ── Step 1: System update ─────────────────────────────────────────────────────
header "Step 1 — Update package list"
sudo apt-get update -qq
ok "Package list updated."

# ── Step 2: Core build tools ──────────────────────────────────────────────────
header "Step 2 — Core build tools"

PACKAGES=(
    # Compiler
    build-essential       # gcc, g++, make
    g++                   # explicit g++ (ensures latest)

    # Build system
    ninja-build           # faster than make, used by CMake presets

    # Version control
    git

    # Utilities
    curl
    wget
    pkg-config
    software-properties-common
)

log "Installing: ${PACKAGES[*]}"
sudo apt-get install -y --no-install-recommends "${PACKAGES[@]}"
ok "Core build tools installed."

# ── Step 3: CMake (minimum 3.22) ─────────────────────────────────────────────
header "Step 3 — CMake (min 3.22)"

install_cmake_from_kitware() {
    log "Adding Kitware APT repository for latest CMake..."
    wget -qO- https://apt.kitware.com/keys/kitware-archive-latest.asc \
        | sudo gpg --dearmor -o /usr/share/keyrings/kitware-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/kitware-archive-keyring.gpg] \
https://apt.kitware.com/ubuntu/ $(lsb_release -cs) main" \
        | sudo tee /etc/apt/sources.list.d/kitware.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y cmake
}

if command -v cmake &>/dev/null; then
    CMAKE_VER=$(cmake --version | head -1 | grep -oP '\d+\.\d+')
    CMAKE_MAJOR=$(echo "$CMAKE_VER" | cut -d. -f1)
    CMAKE_MINOR=$(echo "$CMAKE_VER" | cut -d. -f2)
    if (( CMAKE_MAJOR > 3 )) || (( CMAKE_MAJOR == 3 && CMAKE_MINOR >= 22 )); then
        ok "CMake $CMAKE_VER already installed (meets minimum 3.22)."
    else
        warn "CMake $CMAKE_VER is too old (need 3.22+). Upgrading via Kitware repo..."
        install_cmake_from_kitware
        ok "CMake upgraded."
    fi
else
    log "CMake not found. Installing via Kitware repo..."
    install_cmake_from_kitware
    ok "CMake installed."
fi

# ── Step 4: Python 3.11+ ─────────────────────────────────────────────────────
header "Step 4 — Python 3.11+"

install_python() {
    log "Adding deadsnakes PPA for Python 3.11..."
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update -qq
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11
}

if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if (( PY_MAJOR > 3 )) || (( PY_MAJOR == 3 && PY_MINOR >= 11 )); then
        ok "Python $PY_VER already installed (meets minimum 3.11)."
        python3 -m pip --version &>/dev/null || {
            log "pip not found. Installing..."
            curl -sS https://bootstrap.pypa.io/get-pip.py | python3
        }
    else
        warn "Python $PY_VER is too old (need 3.11+). Installing 3.11 via deadsnakes..."
        install_python
        ok "Python 3.11 installed."
    fi
else
    log "Python not found. Installing 3.11..."
    install_python
    ok "Python 3.11 installed."
fi

# ── Step 5: pip packages needed by the toolchain ─────────────────────────────
header "Step 5 — Python toolchain packages"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="$SCRIPT_DIR/../generated/linux-requirements.json"
export REQ_FILE

python3 - <<'PYEOF'
import json, subprocess, sys, os

req_file = os.environ.get("REQ_FILE")
if not req_file or not os.path.exists(req_file):
    print(f"ERROR: Requirements file missing: {req_file}")
    sys.exit(1)

try:
    with open(req_file) as f:
        data = json.load(f)
except Exception as e:
    print(f"ERROR: Failed to parse JSON: {e}")
    sys.exit(1)

# Pull python packages array
pkgs = data.get("pip", [])
if not pkgs:
    print("No pip packages defined.")
    sys.exit(0)

specs = [
    f"{p['name']}=={p['version']}"
    if isinstance(p, dict) and p.get("version") and p["version"] != "latest"
    else p["name"] if isinstance(p, dict)
    else p
    for p in pkgs
]

print(f" Installing pip packages: {' '.join(specs)}")
try:
    subprocess.run(
        [sys.executable, "-m", "pip", "install"] + specs + ["--break-system-packages"],
        check=True
    )
except subprocess.CalledProcessError as e:
    sys.exit(e.returncode)
PYEOF


# ── Step 5b — Linux system packages (Using Your Heredoc Strategy!) ───────────
header "Step 5b — Installing Dependencies from configuration mapping"

python3 - <<'PYEOF'
import json, subprocess, sys, os

req_file = os.environ.get("REQ_FILE")
try:
    with open(req_file) as f:
        data = json.load(f)
except Exception as e:
    print(f"ERROR: Failed to read requirements: {e}")
    sys.exit(1)

# Pull apt system packages array
packages = data.get("packages", [])
if not packages:
    print("No system packages defined.")
    sys.exit(0)

# Extract name safely whether it's a raw string or dictionary
extracted = [p["name"] if isinstance(p, dict) and "name" in p else p for p in packages if p]
sys_pkgs = [p for p in extracted if isinstance(p, str)]

if sys_pkgs:
    print(f"Installing Linux system targets: {' '.join(sys_pkgs)}")
    try:
        subprocess.run(["sudo", "apt-get", "install", "-y"] + sys_pkgs, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
else:
    print("No valid system packages found to install.")
PYEOF

# ── Step 6: Verify everything ─────────────────────────────────────────────────
header "Step 6 — Verification"

check() {
    local name="$1"
    local cmd="$2"
    if result=$(eval "$cmd" 2>/dev/null); then
        echo -e "  ${GREEN}✓${RESET} $name: $result"
    else
        echo -e "  ${RED}✗${RESET} $name: NOT FOUND"
    fi
}

check "gcc"     "gcc --version | head -1"
check "g++"     "g++ --version | head -1"
check "cmake"   "cmake --version | head -1"
check "ninja"   "ninja --version"
check "git"     "git --version"
check "python3" "python3 --version"
check "pip"     "python3 -m pip --version | head -1"
check "curl"    "curl --version | head -1"

# ── Done ──────────────────────────────────────────────────────────────────────
header "Done"
echo -e "  ${GREEN}All prerequisites installed.${RESET}"
echo ""
echo -e "  Next step:"
echo -e "  ${CYAN}./dev-setup.sh${RESET}   ← install project dependencies"
echo ""