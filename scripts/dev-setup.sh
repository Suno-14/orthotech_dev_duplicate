#!/usr/bin/env bash
# ==============================================================================
# dev-setup.sh — One-time dependency installer for Linux
# Reads: generated/linux-requirements.json
# Installs to: /opt/orthotech_dev
#
# Usage:
#   chmod +x config/dev-setup.sh
#   ./config/dev-setup.sh [OPTIONS]
#
# Options:
#   --regen        Re-run generate_requirements.py before setup
#   --clean        Wipe /opt/orthotech_dev and rebuild everything from scratch
#   --build        Configure + build the project after deps are installed
#   --test         Run tests after build (implies --build)
#   --help         Show this help
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

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REQ_FILE="${REPO_ROOT}/generated/linux-requirements.json"
INSTALL_PREFIX="/opt/orthotech_dev"
SOURCE_CACHE="${INSTALL_PREFIX}/src"
BUILD_DIR="${REPO_ROOT}/build"

# ── Flags ─────────────────────────────────────────────────────────────────────
REGEN=false; CLEAN=false; DO_BUILD=false; DO_TEST=false

for arg in "$@"; do
  case "$arg" in
    --regen) REGEN=true ;;
    --clean) CLEAN=true ;;
    --build) DO_BUILD=true ;;
    --test)  DO_TEST=true; DO_BUILD=true ;;
    --help)
      grep "^#" "$0" | grep -v "^#!/" | sed 's/^# \?//'
      exit 0 ;;
    *) err "Unknown option: $arg" ;;
  esac
done

# ── Sanity checks ─────────────────────────────────────────────────────────────
header "orthotech_dev — Linux Dev Setup"
command -v python3 &>/dev/null || err "python3 not found."
command -v git     &>/dev/null || err "git not found."
command -v cmake   &>/dev/null || warn "cmake not found — will be installed via apt."

log "Repo root      : ${REPO_ROOT}"
log "Install prefix : ${INSTALL_PREFIX}"
log "Requirements   : ${REQ_FILE}"

# ── Step 1: Regen ─────────────────────────────────────────────────────────────
header "Step 1 — Requirements"
if [[ "$REGEN" == "true" || ! -f "$REQ_FILE" ]]; then
  log "Running generate_requirements.py..."
  python3 -m pip install --quiet pyyaml
  python3 "${SCRIPT_DIR}/generate_requirements.py" --validate
  ok "Requirements generated."
else
  log "linux-requirements.json exists. Use --regen to regenerate."
fi

# ── Step 2: Clean ─────────────────────────────────────────────────────────────
if [[ "$CLEAN" == "true" ]]; then
  warn "--clean: removing ${INSTALL_PREFIX}"
  sudo rm -rf "${INSTALL_PREFIX}"
fi

sudo mkdir -p "${INSTALL_PREFIX}" "${SOURCE_CACHE}"
sudo chown -R "${USER}:${USER}" "${INSTALL_PREFIX}"

# ── Step 3: apt packages ──────────────────────────────────────────────────────
header "Step 2 — apt packages"
python3 - <<PYEOF
import json, subprocess, sys

with open("${REQ_FILE}") as f:
    data = json.load(f)

pkgs = [p["name"] for p in data.get("packages", [])]
if not pkgs:
    print("  No apt packages defined.")
    sys.exit(0)

print(f"  Installing: {' '.join(pkgs)}")
subprocess.run(["sudo", "apt-get", "update", "-qq"], check=True)
subprocess.run([
    "sudo", "apt-get", "install", "-y", "--no-install-recommends"
] + pkgs, check=True)
PYEOF
ok "apt packages done."

# ── Step 4: pip packages ──────────────────────────────────────────────────────
header "Step 3 — pip packages"
python3 - <<PYEOF
import json, subprocess, sys

with open("${REQ_FILE}") as f:
    data = json.load(f)

pkgs = data.get("pip", [])
if not pkgs:
    print("  No pip packages defined.")
    sys.exit(0)

specs = [
    f"{p['name']}=={p['version']}" if p.get("version") and p["version"] != "latest"
    else p["name"]
    for p in pkgs
]
print(f"  Installing: {' '.join(specs)}")
subprocess.run([sys.executable, "-m", "pip", "install"] + specs, check=True)
PYEOF
ok "pip packages done."

# ── Step 5: source builds ─────────────────────────────────────────────────────
header "Step 4 — Source builds"
python3 - <<PYEOF
import json, os, subprocess, sys, shlex
from pathlib import Path

install_prefix = Path("${INSTALL_PREFIX}")
source_cache   = Path("${SOURCE_CACHE}")

with open("${REQ_FILE}") as f:
    data = json.load(f)

deps = data.get("source", [])
if not deps:
    print("  No source deps defined.")
    sys.exit(0)

for dep in deps:
    name = dep["name"]
    tag  = dep["tag"]
    stamp = source_cache / f".{name}-{tag}.stamp"

    if stamp.exists():
        print(f"  [SKIP] {name}@{tag} already installed.")
        continue

    print(f"\n  [BUILD] {name}@{tag}")

    src_dir = source_cache / f"{name}"
    if not src_dir.exists():
        subprocess.run([
            "git", "clone", "--depth=1", "--branch", tag,
            dep["repo"], str(src_dir)
        ], check=True)
    else:
        # already cloned — checkout correct tag
        subprocess.run(["git", "-C", str(src_dir), "fetch",
                        "--depth=1", "origin", tag], check=True)
        subprocess.run(["git", "-C", str(src_dir), "checkout", tag], check=True)

    build_root = src_dir / (dep.get("build_dir") or "")
    build_dir  = src_dir / "_build"
    build_dir.mkdir(exist_ok=True)

    cmake_extra = shlex.split(dep.get("cmake_args") or "")
    subprocess.run([
        "cmake", "-S", str(build_root), "-B", str(build_dir),
        "-GNinja",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={install_prefix}",
    ] + cmake_extra, check=True)

    subprocess.run([
        "cmake", "--build", str(build_dir),
        "--config", "Release",
        "--parallel", str(os.cpu_count())
    ], check=True)

    subprocess.run([
        "cmake", "--install", str(build_dir)
    ], check=True)

    # post_install hook (e.g. ldconfig)
    post = dep.get("post_install", "").strip()
    if post:
        print(f"  [POST] {post}")
        subprocess.run(post, shell=True, check=True)

    stamp.touch()
    print(f"  [OK] {name} installed to {install_prefix}")

print(f"\n  All source deps installed to {install_prefix}")
PYEOF
ok "Source builds done."

# ── Step 6: optional project build ───────────────────────────────────────────
if [[ "$DO_BUILD" == "true" ]]; then
  header "Step 5 — Build project"
  cmake --preset linux-release \
    -DCMAKE_PREFIX_PATH="${INSTALL_PREFIX}"
  cmake --build "${BUILD_DIR}" --config Release --parallel 8
  ok "Project built."
fi

# ── Step 7: optional tests ────────────────────────────────────────────────────
if [[ "$DO_TEST" == "true" ]]; then
  header "Step 6 — Tests"
  ctest --test-dir "${BUILD_DIR}" --output-on-failure --parallel 8
  ok "Tests passed."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
header "Done"
echo -e "  ${GREEN}All dependencies installed to ${BOLD}${INSTALL_PREFIX}${RESET}"
echo ""
echo -e "  Add this to your CMake configure step if not using presets:"
echo -e "  ${CYAN}cmake -S . -B build -DCMAKE_PREFIX_PATH=\"${INSTALL_PREFIX}\"${RESET}"
echo ""
