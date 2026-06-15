#!/usr/bin/env python3
import sys
import os
import platform
import subprocess
import argparse
import json
from pathlib import Path

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

def run_script(cmd, shell=False,env=None):
    """Executes a terminal or shell script cleanly."""
    print(f"\n Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, shell=shell, env=env)
    if result.returncode != 0:
        print(f" Error: Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)

def generate_requirements():
    """
    Generate platform requirements JSON files from dependencies.yml.
    Must run before any dev-setup script — both Linux and Windows
    setup scripts depend on the generated JSON files.
    """
    print("\n Generating platform requirements from dependencies.yml...")

    req_script = Path("scripts/generate_requirements.py")
    config     = Path("config/dependencies.yml")

    if not req_script.exists():
        print(f" Error: {req_script} not found.")
        sys.exit(1)

    if not config.exists():
        print(f" Error: {config} not found.")
        sys.exit(1)

    # Ensure pyyaml is available
    try:
        import yaml  # noqa: F401
    except ImportError:
        print(" [INFO] pyyaml not found. Installing...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyyaml"],
            check=True
        )

    run_script([
        sys.executable,
        str(req_script),
        "--config", str(config),
        "--validate"
    ])

    # Verify output files actually exist
    linux_out   = Path("generated/linux-requirements.json")
    windows_out = Path("generated/windows-requirements.json")

    if not linux_out.exists() or not windows_out.exists():
        print(" Error: Requirements files were not generated correctly.")
        sys.exit(1)

    print(" Requirements generated successfully.")

def update_submodules():
    """Reads submodule_branches.json and dynamically forces each submodule
    to track and pull its explicitly mapped development/production branch."""
    json_path = Path("config/submodule_branches.json")

    if not json_path.exists():
        print(f"  [GIT] Warning: '{json_path}' not found. Falling back to standard update.")
        try:
            subprocess.run(["git", "submodule", "update", "--init", "--recursive"], check=True)
            return
        except subprocess.CalledProcessError:
            sys.exit(1)

    print(f"\n [GIT] Loading branch mappings from {json_path}...")
    with open(json_path, "r", encoding="utf-8") as f:
        submodule_map = json.load(f)

    try:
        # 1. Initialize all submodules structural frameworks first
        subprocess.run(["git", "submodule", "init"], check=True)

        # 2. Iterate through each submodule and point Git to the mapped branch
        for sub_path, branch_name in submodule_map.items():
            normalized_path = os.path.normpath(sub_path)

            # Skip root repo tracking
            if sub_path.lower() == "software" or normalized_path == ".":
                print("  [GIT] Skipping root repository pointer ('Software')")
                continue

            print(f" [GIT] Configuring tracking: {normalized_path} → branch: [{branch_name}]")

            subprocess.run([
                "git", "submodule", "set-branch",
                "--branch", branch_name,
                normalized_path
            ], check=True)

        # 3. Pull all submodules to their mapped branches
        print("\n [GIT] Pulling latest remote changes for all submodules...")
        subprocess.run([
            "git", "submodule", "update",
            "--init",
            "--recursive",
            "--remote",
            "--merge"
        ], check=True)

        print("[GIT] All submodules successfully updated to their mapped branches!")

    except subprocess.CalledProcessError as e:
        print(f" Error updating branch-mapped submodules: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Unified Orthotech Setup & Management Toolchain")
    parser.add_argument("--skip-prereqs", action="store_true", help="Skip system prerequisites check/install")
    parser.add_argument("--skip-pull",    action="store_true", help="Skip pulling/updating recursive Git submodules")
    parser.add_argument("--skip-regen",   action="store_true", help="Skip requirements regeneration (use existing JSON files)")

    # Platform overrides
    parser.add_argument("--windows", action="store_true", help="Force target execution configuration for Windows")
    parser.add_argument("--linux",   action="store_true", help="Force target execution configuration for Linux")

    args = parser.parse_args()

    # Determine execution platform
    if args.windows and args.linux:
        print(" Error: You cannot specify both --windows and --linux simultaneously.")
        sys.exit(1)
    elif args.windows:
        target_os = "Windows"
        print(" Platform Overridden: Forcing execution target to Windows.")
    elif args.linux:
        target_os = "Linux"
        print(" Platform Overridden: Forcing execution target to Linux.")
    else:
        target_os = platform.system()

    print(f" Starting Orthotech Master Toolchain for target environment: {target_os}...")

    # Step 1: Manage Git Submodules
    if not args.skip_pull:
        update_submodules()
    else:
        print("\n Skipping Git submodule pull step (handled by caller environment).")

    # Step 2: Check admin privileges (only needed for prerequisite installs)
    if not args.skip_prereqs and not is_admin():
        if target_os == "Windows":
            print(" Error: You must run this script from an Administrator PowerShell prompt.")
        else:
            print(" Error: You must run this script with sudo (e.g., sudo python3 setup_all.py).")
        sys.exit(1)

    # Step 3: Generate requirements JSON
    # Always runs unless explicitly skipped — dev-setup scripts depend on these files.
    if not args.skip_regen:
        generate_requirements()
    else:
        # Verify the files exist even if we're skipping regen
        linux_out   = Path("generated/linux-requirements.json")
        windows_out = Path("generated/windows-requirements.json")
        missing = []
        if not linux_out.exists():   missing.append(str(linux_out))
        if not windows_out.exists(): missing.append(str(windows_out))
        if missing:
            print(f" Error: --skip-regen was set but these files are missing:")
            for m in missing:
                print(f"   {m}")
            print(" Remove --skip-regen or commit the generated files to the repo.")
            sys.exit(1)
        print("\n Skipping requirements regeneration (using existing JSON files).")

    # Step 4: Run platform-specific setup
    if target_os == "Windows":
        if not args.skip_prereqs:
            run_script(["powershell", "-ExecutionPolicy", "Bypass",
                        "-File", "scripts/install-prerequisites.ps1"])

        print("\n Processing Windows build configuration...")
        
        # 🌟 Create a copy of the existing environment variables and add UTF-8 forced compliance
        win_env = os.environ.copy()
        win_env["PYTHONUTF8"] = "1"
        
        # Pass win_env into your updated run_script function
        run_script(["powershell", "-ExecutionPolicy", "Bypass",
                    "-File", "scripts/dev-setup.ps1", "-Build", "-Test"], env=win_env)

    elif target_os == "Linux":
        if not args.skip_prereqs:
            run_script(["bash", "scripts/install-prerequisites.sh"])

        print("\n Processing Linux build configuration...")
        run_script(["bash", "scripts/dev-setup.sh", "--build", "--test"])

    else:
        print(f" Unsupported Operating System Configuration: {target_os}")
        sys.exit(1)

    print(f"\n [SUCCESS] Workspace environment for {target_os} fully updated and compiled!")

if __name__ == "__main__":
    main()