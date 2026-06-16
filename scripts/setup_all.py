#!/usr/bin/env python3
import sys
import os
import platform
import subprocess
import argparse
import json
from pathlib import Path
import time
import shutil

BASE_DIR = Path(__file__).resolve().parent.parent

def is_admin():
    """Checks for Administrator / Root permissions."""
    try:
        if platform.system() == "Windows":
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.getuid() == 0
    except Exception:
        return False

def run_script(cmd, shell=False, env=None, retries=2, timeout=120):
    """Robust command runner with retries, full output capture, and proper error propagation."""

    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
    print(f"\n[RUN] {cmd_str}")

    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                cmd,
                shell=shell,
                env=env,
                timeout=timeout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode == 0:
                if result.stdout:
                    print(result.stdout)
                return

            print(result.stdout)
            print(result.stderr)

            print(f"[FAIL] exit={result.returncode} (Attempt {attempt + 1}/{retries + 1})")

        except subprocess.TimeoutExpired as e:
            print(f"[TIMEOUT] Command exceeded {timeout}s")
            print(e)

        if attempt < retries:
            time.sleep(2)
        else:
            print("[ERROR] Command failed permanently after maximum retry allocations.")

            raise RuntimeError(f"Command failed: {cmd_str}")

def generate_requirements():
    """Generate platform requirements JSON files from dependencies.yml."""
    print("\n Generating platform requirements from dependencies.yml...")

    req_script = BASE_DIR / "scripts/generate_requirements.py"
    config     = BASE_DIR / "config/dependencies.yml"

    if not req_script.exists() or not config.exists():
        print(f" Error: Vital prerequisite toolchain files are missing.")
        sys.exit(1)

    try:
        import yaml  # noqa: F401
    except ImportError:
        print(" [INFO] pyyaml not found. Installing configuration parser dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyyaml"], check=True)

    run_script([
        sys.executable,
        str(req_script),
        "--config", str(config),
        "--validate"
    ])

    linux_out   = BASE_DIR / "generated/linux-requirements.json"
    windows_out = BASE_DIR / "generated/windows-requirements.json"

    if not linux_out.exists() or not windows_out.exists():
        print(" Error: Requirements files were not generated correctly.")
        sys.exit(1)

    print(" Requirements generated successfully.")

def normalize_repo_url(repo):
    """Prevents credential prompts by changing raw SSH to secure HTTPS formats."""
    if repo and repo.startswith("git@github.com:"):
        return repo.replace("git@github.com:", "https://github.com/")
    return repo

def get_commit(path):
    """Retrieves current tracking commit hashes cleanly via Path targeting."""
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True
        ).strip()
    except:
        return None

def is_valid_submodule(path):
    """Verifies that an allocated path is a synchronized Git target index."""
    return subprocess.run(
        ["git", "submodule", "status", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ).returncode == 0

def update_submodules():
    """Reads submodule configurations and establishes uniform tracking states."""
    json_path = BASE_DIR / "config/submodule_branches.json"

    if not json_path.exists():
        print(f"[GIT] Missing validation configuration: {json_path}")
        sys.exit(1)

    # Inject safe directory assignment
    run_script(["git", "config", "--global", "--add", "safe.directory", str(BASE_DIR)])

    print(f"\n[GIT] Loading track layouts from {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        submodule_map = json.load(f)

    try:
        for sub_name, config in submodule_map.items():
            if isinstance(config, dict):
                branch = config.get("branch", "main")
                repo   = config.get("url")
                sub_path = config.get("path", f"src/{sub_name}")
            else:
                branch = config
                repo   = None
                sub_path = sub_name

            # Enforce modern clean pathlib conversions
            target_path = Path(sub_path).resolve()
            repo = normalize_repo_url(repo)

            print(f"\n[GIT] Processing Workspace Path: {sub_path} (target-branch={branch})")

            # Ensure tracking base layer is structured
            target_path.parent.mkdir(parents=True, exist_ok=True)

            old_commit = get_commit(target_path) if target_path.exists() else None

            # Self-healing clean step for corrupted modules
            if target_path.exists() and not is_valid_submodule(sub_path):
                print(f"  [CORRUPT] Found incomplete metadata layouts. Purging path: {sub_path}")
                run_script(["git", "submodule", "deinit", "-f", sub_path])
                shutil.rmtree(target_path, ignore_errors=True)

            # Clone tracking branches for unmapped/new modules
            if not target_path.exists():
                if not repo:
                    print(f"  [WARN] Missing tracking URL destination profile for {sub_path}, skipping.")
                    continue

                print(f"  [PROVISIONING NEW MODULE] Adding {sub_path}")
                run_script([
                    "git", "submodule", "add",
                    "-b", branch,
                    "--force",
                    repo,
                    sub_path
                ])

            run_script(["git", "submodule", "sync", "--recursive", sub_path])
            run_script(["git", "submodule", "init", sub_path])
            run_script(["git", "submodule", "set-branch", "--branch", branch, sub_path])
            run_script(["git", "submodule", "update", "--init", "--recursive", "--remote", "--merge", sub_path])

            new_commit = get_commit(target_path)

            if old_commit is None:
                print(f"  [NEW] {sub_path} tracking started at @ {new_commit[:8]}")
            elif old_commit == new_commit:
                print(f"  [UNCHANGED] {sub_path} remains lock-synchronized ({new_commit[:8]})")
            else:
                print(f"  [UPDATED DELTA DETECTED] {sub_path}")
                print(f"    History state shift: {old_commit[:8]} → {new_commit[:8]}")

                try:
                    log = subprocess.check_output([
                        "git", "-C", str(target_path),
                        "log", "--oneline", "--max-count=5",
                        f"{old_commit}..{new_commit}"
                    ], text=True)

                    print("    Changelog summary:")
                    for line in log.splitlines():
                        print(f"      {line}")
                except:
                    pass

        print("\n[GIT] All targeted submodules synchronized cleanly.")

    except Exception as e:
        print(f"\n[ERROR] Pipeline tracking broke during updates: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Unified Orthotech Setup & Management Toolchain")
    parser.add_argument("--skip-prereqs", action="store_true", help="Skip system prerequisites check/install")
    parser.add_argument("--skip-pull",    action="store_true", help="Skip pulling/updating recursive Git submodules")
    parser.add_argument("--skip-regen",   action="store_true", help="Skip requirements regeneration (use existing JSON files)")

    parser.add_argument("--windows", action="store_true", help="Force target execution configuration for Windows")
    parser.add_argument("--linux",   action="store_true", help="Force target execution configuration for Linux")

    args = parser.parse_args()

    if args.windows and args.linux:
        print(" Error: You cannot specify both --windows and --linux simultaneously.")
        sys.exit(1)
    elif args.windows:
        target_os = "Windows"
    elif args.linux:
        target_os = "Linux"
    else:
        target_os = platform.system()

    print(f" Starting Orthotech Master Toolchain for target environment: {target_os}...")

    if not args.skip_pull:
        update_submodules()
    else:
        print("\n Skipping Git submodule pull step (handled by caller environment).")

    if not args.skip_prereqs and target_os == "Windows" and not is_admin():
        print("\n Error: You must run this script from an Administrator PowerShell prompt on Windows.")
        sys.exit(1)

    if not args.skip_regen:
        generate_requirements()
    else:
        linux_out   = BASE_DIR / "generated/linux-requirements.json"
        windows_out = BASE_DIR / "generated/windows-requirements.json"
        missing = []
        if not linux_out.exists():   missing.append(str(linux_out))
        if not windows_out.exists(): missing.append(str(windows_out))
        if missing:
            print(f" Error: --skip-regen was set but these files are missing:")
            for m in missing:
                print(f"   {m}")
            sys.exit(1)
        print("\n Skipping requirements regeneration (using existing JSON files).")

    if target_os == "Windows":
        if not args.skip_prereqs:
            run_script(["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/install-prerequisites.ps1"])

        print("\n Processing Windows build configuration...")
        win_env = os.environ.copy()
        win_env["PYTHONUTF8"] = "1"
        run_script(["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/dev-setup.ps1", "-Build", "-Test"], env=win_env)

    elif target_os == "Linux":
        if not args.skip_prereqs:
            run_script(["bash", "scripts/install-prerequisites.sh"])

        print("\n Processing Linux build configuration...")
        linux_cmd = ["bash", "scripts/dev-setup.sh", "--build", "--test"]
        # if args.skip_prereqs:
        #     linux_cmd.append("--skip-prereqs")
        run_script(linux_cmd)
    else:
        print(f" Unsupported Operating System Configuration: {target_os}")
        sys.exit(1)

    print(f"\n [SUCCESS] Workspace environment for {target_os} fully updated and compiled!")

if __name__ == "__main__":
    main()