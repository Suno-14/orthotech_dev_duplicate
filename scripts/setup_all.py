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
    """Reads submodule_branches.json and dynamically ensures ONLY mapped 
    submodules are cloned, tracked, and pulled."""
    json_path = Path("config/submodule_branches.json")

    # If the JSON is missing, crash immediately instead of doing a loose global sync!
    if not json_path.exists():
        print(f"  [GIT] Error: Critical configuration '{json_path}' is missing! Aborting.")
        sys.exit(1)

    print(f"\n [GIT] Loading branch mappings from {json_path}...")
    with open(json_path, "r", encoding="utf-8") as f:
        submodule_map = json.load(f)

    try:
        for sub_name, config in submodule_map.items():
            if isinstance(config, dict):
                branch_name = config.get("branch", "main")
                repo_url = config.get("url")
                sub_path = config.get("path", f"src/{sub_name}")
            else:
                branch_name = config
                repo_url = None
                sub_path = sub_name

            normalized_path = os.path.normpath(sub_path)

            # Only add it if it's missing AND explicitly declared with a URL here
            if not os.path.exists(normalized_path) or not os.listdir(normalized_path):
                if repo_url:
                    print(f" [GIT] New submodule detected in JSON! Provisioning '{normalized_path}'...")
                    subprocess.run([
                        "git", "submodule", "add", "-b", branch_name, repo_url, normalized_path
                    ], check=True)
                else:
                    continue
            else:
                subprocess.run(["git", "submodule", "init", normalized_path], check=True)

            # Set tracking branch specifically for THIS submodule path
            subprocess.run(["git", "submodule", "set-branch", "--branch", branch_name, normalized_path], check=True)
            
            # Explicitly target ONLY this specific path during updates!
            print(f" [GIT] Updating targeted submodule: {normalized_path}")
            subprocess.run([
                "git", "submodule", "update", "--init", "--recursive", "--remote", "--merge", normalized_path
            ], check=True)

        print("[GIT] All JSON-defined submodules successfully synchronized!")

    except subprocess.CalledProcessError as e:
        print(f" Error executing Git automation pipeline: {e}")
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
    # if not args.skip_prereqs and not is_admin():
    #     if target_os == "Windows":
    #         print(" Error: You must run this script from an Administrator PowerShell prompt.")
    #     else:
    #         print(" Error: You must run this script with sudo (e.g., sudo python3 setup_all.py).")
    #     sys.exit(1)
    if not args.skip_prereqs and target_os == "Windows" and not is_admin():
        print("\n Error: You must run this script from an Administrator PowerShell prompt on Windows.")
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
        
        # Create a copy of the existing environment variables and add UTF-8 forced compliance
        win_env = os.environ.copy()
        win_env["PYTHONUTF8"] = "1"
        
        # Pass win_env into your updated run_script function
        run_script(["powershell", "-ExecutionPolicy", "Bypass",
                    "-File", "scripts/dev-setup.ps1", "-Build", "-Test"], env=win_env)

    elif target_os == "Linux":
        if not args.skip_prereqs:
            run_script(["bash", "scripts/install-prerequisites.sh"])

        print("\n Processing Linux build configuration...")
        linux_cmd = ["bash", "scripts/dev-setup.sh", "--build", "--test"]
        if args.skip_prereqs:
            linux_cmd.append("--skip-prereqs")
            
        run_script(linux_cmd)

    else:
        print(f" Unsupported Operating System Configuration: {target_os}")
        sys.exit(1)

    print(f"\n [SUCCESS] Workspace environment for {target_os} fully updated and compiled!")

if __name__ == "__main__":
    main()