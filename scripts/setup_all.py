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

def run_script(cmd, shell=False):
    """Executes a terminal or shell script cleanly."""
    print(f"\n Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, shell=shell)
    if result.returncode != 0:
        print(f" Error: Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)

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
        
        # 2. Iterate through each submodule and dynamically point Git to the mapped branch
        for sub_path, branch_name in submodule_map.items():
            # Standardize path string for both Windows and Linux environments
            normalized_path = os.path.normpath(sub_path)
            
            # DEFENSIVE GUARD: Skip the root repo tracking if it is named "Software" or "."
            if sub_path.lower() == "software" or normalized_path == ".":
                print("  [GIT] Skipping root repository pointer ('Software')")
                continue

            print(f" [GIT] Configuring tracking: {normalized_path} ➔ branch: [{branch_name}]")
            
            # Explicitly modify git's branch assignment config for this individual submodule
            subprocess.run([
                "git", "submodule", "set-branch", 
                "--branch", branch_name, 
                normalized_path
            ], check=True)

        # 3. Execute a master recursive pull to synchronize all floating targets simultaneously
        print("\n [GIT] Pulling latest remote changes for all submodules...")
        subprocess.run([
            "git", "submodule", "update", 
            "--init", 
            "--recursive", 
            "--remote",   # Pulls fresh remote upstream tracking branches
            "--merge"     # Merges updates directly down into local workspace states
        ], check=True)
        
        print("[GIT] All submodules successfully updated to their mapped branches!")
        
    except subprocess.CalledProcessError as e:
        print(f" Error updating branch-mapped submodules: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Unified Orthotech Setup & Management Toolchain")
    parser.add_argument("--skip-prereqs", action="store_true", help="Skip system prerequisites check/install")
    parser.add_argument("--skip-pull", action="store_true", help="Skip pulling/updating recursive Git submodules")
    
    # Platform Overrides
    parser.add_argument("--windows", action="store_true", help="Force target execution configuration for Windows")
    parser.add_argument("--linux", action="store_true", help="Force target execution configuration for Linux")
    
    args = parser.parse_args()

    # Determine execution platform target
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
        # Fallback to automatic runtime detection if no override flag is present
        target_os = platform.system()

    print(f" Starting Orthotech Master Toolchain for target environment: {target_os}...")

    # Step 1: Manage Git Submodules (skipped in Actions via --skip-pull)
    if not args.skip_pull:
        update_submodules()
    else:
        print("\n Skipping Git submodule pull step (handled by caller environment).")

    # Step 2: Enforce Admin privileges ONLY if installing system prerequisites
    if not args.skip_prereqs and not is_admin():
        if target_os == "Windows":
            print(" Error: You must run this script from an Administrator PowerShell prompt.")
        else:
            print(" Error: You must run this script with sudo (e.g., sudo python3 setup_all.py).")
        sys.exit(1)

    # Step 3: Run Setup Scripts based on Chosen Target Platform
    if target_os == "Windows":
        if not args.skip_prereqs:
            run_script(["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/install-prerequisites.ps1"])
        
        print("\n Processing Windows build configuration...")
        run_script(["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/dev-setup.ps1", "-Build", "-Test"])

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