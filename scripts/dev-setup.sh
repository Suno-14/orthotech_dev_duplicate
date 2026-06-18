#!/usr/bin/env bash
# ==============================================================================
# dev-setup.sh — One-time dependency installer for Linux
# Reads: generated/linux-requirements.json
# Installs to: /opt/orthotech_dev
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
SOURCE_CACHE="${INSTALL_PREFIX}/thirdparty"
BUILD_DIR="${REPO_ROOT}/build"

export REQ_FILE INSTALL_PREFIX SOURCE_CACHE

if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "[INFO] Running on GitHub Actions"
    SKIP_APT_INSTALL=1
fi
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

# ── Step 1: Verify Requirements ───────────────────────────────────────────────
header "Step 1 — Verify Requirements"

if [[ ! -f "$REQ_FILE" ]]; then
  err "Requirements file missing: $REQ_FILE. Please run setup_all.py first."
fi
ok "Found generated requirements file."

# ── Step 2: Clean ─────────────────────────────────────────────────────────────
if [[ "$CLEAN" == "true" ]]; then
  warn "--clean: removing ${INSTALL_PREFIX}"
  sudo rm -rf "${INSTALL_PREFIX}"
fi

sudo mkdir -p "${INSTALL_PREFIX}" "${SOURCE_CACHE}"
sudo chown -R "${USER}:${USER}" "${INSTALL_PREFIX}"

# ── Step 3: apt packages ──────────────────────────────────────────────────────
if [[ "${SKIP_APT_INSTALL:-0}" != "1" ]]; then
header "Step 2 — apt packages"
python3 - <<'PYEOF'
import json, subprocess, sys, os

req_file = os.environ.get("REQ_FILE")
with open(req_file) as f:
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
fi


# ── Step 4: pip packages ──────────────────────────────────────────────────────
header "Step 3 — pip packages"
python3 - <<'PYEOF'
import json, subprocess, sys, os

req_file = os.environ.get("REQ_FILE")
with open(req_file) as f:
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
subprocess.run([sys.executable, "-m", "pip", "install"] + specs + ["--break-system-packages"], check=True)
PYEOF
ok "pip packages done."

# ── Step 5: source builds ─────────────────────────────────────────────────────
header "Step 4 — Source builds"
python3 - <<'PYEOF'
import json, os, subprocess, sys, shlex, hashlib, shutil, time
from pathlib import Path

install_prefix = Path(os.environ.get("INSTALL_PREFIX"))
source_cache   = Path(os.environ.get("SOURCE_CACHE"))
req_file       = Path(os.environ.get("REQ_FILE"))

log_dir = source_cache / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# Utility: robust command runner
# ─────────────────────────────────────────────────────────────
def run(cmd, *, cwd=None, retries=0, timeout=None, logfile=None, name=""):
    is_shell = isinstance(cmd, str)
    cmd_printable = cmd if is_shell else " ".join(cmd)
    display_name = name or (cmd if is_shell else cmd[0])

    for attempt in range(retries + 1):
        try:
            print(f"    → {display_name}")
            with open(logfile, "a") if logfile else subprocess.DEVNULL as logf:
                subprocess.run(
                    cmd,
                    cwd=cwd,
                    check=True,
                    timeout=timeout,
                    shell=is_shell,
                    stdout= None,
                    stderr= None
                )
            return
        except subprocess.TimeoutExpired as e:
            print(f"    [TIMEOUT] {cmd_printable}")
            if attempt >= retries:
                raise RuntimeError(f"Command timed out: {cmd_printable}") from e
                
        except subprocess.CalledProcessError as e:
            print(f"    [FAIL] {cmd_printable} (exit={e.returncode})")
            if attempt >= retries:
                raise RuntimeError(f"Step '{display_name}' failed permanently with exit code {e.returncode}") from e

        if attempt < retries:
            print(f"    [RETRY] attempt {attempt+1}/{retries}")
            time.sleep(2)


# ─────────────────────────────────────────────────────────────
# Load config
# ─────────────────────────────────────────────────────────────
with open(req_file) as f:
    data = json.load(f)

deps = data.get("source", [])
if not deps:
    print("  No source deps defined.")
    sys.exit(0)

# Validate required fields
required = ["name", "repo", "tag"]
for dep in deps:
    for key in required:
        if key not in dep:
            raise ValueError(f"Missing '{key}' in {dep}")

# ─────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────
for dep in deps:
    name = dep["name"]
    tag  = dep["tag"]

    fingerprint = hashlib.sha256(
        json.dumps(dep, sort_keys=True).encode()
    ).hexdigest()[:8]

    stamp = source_cache / f".{name}-{tag}-{fingerprint}.stamp"
    tmp_stamp = stamp.with_suffix(".tmp")
    lock_file = source_cache / f".{name}.lock"
    logfile = log_dir / f"{name}.log"

    if stamp.exists():
        print(f"  [SKIP] {name}@{tag} already installed.")
        continue

    if lock_file.exists():
        raise RuntimeError(f"{name} is already being built (lock exists)")

    lock_file.touch()

    print(f"\n  [BUILD] {name}@{tag}")
    print(f"  [LOG] {logfile}")

    try:
        src_dir = source_cache / name

        if not src_dir.exists():
            run([
                "git", "clone", "--depth=1", "--branch", tag,
                dep["repo"], str(src_dir)
            ], retries=2, timeout=300, logfile=logfile, name="git clone")
        else:
            print(f"    [INFO] Resetting existing repository for {name}...")
            # If the directory exists but checkout is stuck, clean reset it
            run(["git", "-C", str(src_dir), "clean", "-fdx"], logfile=logfile, name="git clean")
            run(["git", "-C", str(src_dir), "fetch", "--tags"], retries=1, timeout=120, logfile=logfile, name="git fetch tags")
            
            try:
                run(["git", "-C", str(src_dir), "checkout", tag], logfile=logfile, name="git checkout")
            except Exception:
                # If checking out a tag fails due to shallow history, pull the full depth as a fallback
                print(f"    [WARN] Shallow history checkout failed. Unshallowing repository...")
                run(["git", "-C", str(src_dir), "fetch", "--unshallow"], retries=1, timeout=300, logfile=logfile, name="git unshallow")
                run(["git", "-C", str(src_dir), "checkout", tag], logfile=logfile, name="git checkout retry")
        
        post_co = dep.get("post_checkout", "").strip()
        if post_co:
            print(f"    [PATCH] Running post-checkout patch: {post_co}")
            run(post_co, cwd=str(src_dir), logfile=logfile, name="post-checkout-patch")

        build_root = src_dir / (dep.get("build_dir") or "")
        build_dir  = src_dir / "_build"

        if build_dir.exists():
            print(f"  [CLEAN] removing old build dir")
            shutil.rmtree(build_dir)

        build_dir.mkdir()

        cmake_extra = shlex.split(dep.get("cmake_args") or "")

        run([
            "cmake",
            "-S", str(build_root),
            "-B", str(build_dir),
            "-GNinja",
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DCMAKE_INSTALL_PREFIX={install_prefix}",
        ] + cmake_extra,
            timeout=300,
            logfile=logfile,
            name="cmake configure"
        )

        run([
            "cmake", "--build", str(build_dir),
            "--parallel", str(os.cpu_count())
        ],
            timeout=1800,
            logfile=logfile,
            name="cmake build"
        )

        run([
            "cmake", "--install", str(build_dir)
        ],
            timeout=300,
            logfile=logfile,
            name="cmake install"
        )

        post = dep.get("post_install", "").strip()
        if post:
            print(f"  [POST] {post}")
            run(post, logfile=logfile, name="post-install", retries=1)

        tmp_stamp.touch()
        tmp_stamp.rename(stamp)

        print(f"  [OK] {name} installed to {install_prefix}")

    except Exception as e:
        print(f"  [ERROR] {name} failed: {e}")
        print(f"  [CLEANUP] removing build dir")

        build_dir = source_cache / name / "_build"
        if build_dir.exists():
            shutil.rmtree(build_dir)

        raise

    finally:
        if lock_file.exists():
            lock_file.unlink()

print(f"\n  All source deps installed to {install_prefix}")
PYEOF
ok "Source builds done."

# ── Step 6: optional project build ───────────────────────────────────────────
if [[ "$DO_BUILD" == "true" ]]; then
  header "Step 5 — Build project"
  cmake -S . --preset linux-release \
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
