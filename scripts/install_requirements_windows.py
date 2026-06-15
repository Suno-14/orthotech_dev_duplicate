#!/usr/bin/env python3
import os
import sys
import json
import shlex
import subprocess
from pathlib import Path
import winreg

def refresh_windows_path():
    """Dynamically reads the live system and user PATH keys from the registry
    and applies them directly to the running python instance memory.
    """
    try:
        # Read Machine Path Environment
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as key:
            machine_path = winreg.QueryValueEx(key, "Path")[0]
        
        # Read User Path Environment
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            user_path = winreg.QueryValueEx(key, "Path")[0]
        
        # Combine them and update active process memory
        os.environ["PATH"] = f"{machine_path};{user_path}"
        print("  [SYSTEM] Environment PATH successfully updated from registry.")
    except Exception as e:
        print(f"  [WARN] Dynamic path refresh skipped: {e}")

def main():
    repo_root = Path(__file__).resolve().parent.parent
    req_file = (repo_root / "generated" / "windows-requirements.json").resolve()
    install_prefix = Path(r"C:\orthotech_dev\deps")
    source_cache = install_prefix / "src"
    source_cache.mkdir(parents=True, exist_ok=True)
    print(f"[Python System] Reading mapped configurations from: {req_file}")
    if not req_file.exists():
        print(f"[ERROR] Requirements file missing: {req_file}")
        sys.exit(1)

    with open(req_file, "r") as f:
        data = json.load(f)

    # 1. AUTOMATED VCPKG SELF-HEALING & INSTALLATION
    vcpkg_root = os.environ.get("VCPKG_ROOT", r"C:\orthotech_dev\vcpkg")
    vcpkg_exe = os.path.join(vcpkg_root, "vcpkg.exe")
    pkgs = data.get("vcpkg", [])

    if pkgs:
        # If vcpkg directory or executable is completely missing, download and build it!
        if not os.path.exists(vcpkg_exe):
            print("\n━━━━━━━ [AUTOMATION] vcpkg Missing! Bootstrapping Engine ━━━━━━━")
            os.makedirs(os.path.dirname(vcpkg_root), exist_ok=True)
            
            if not os.path.exists(vcpkg_root):
                print(f"  Cloning official vcpkg repository into {vcpkg_root}...")
                subprocess.run([
                    "git", "clone", "https://github.com/microsoft/vcpkg.git", vcpkg_root
                ], check=True, shell=True)
            
            print("  Compiling vcpkg core executable engine...")
            bootstrap_script = os.path.join(vcpkg_root, "bootstrap-vcpkg.bat")
            subprocess.run([bootstrap_script], check=True, shell=True, cwd=vcpkg_root)
            print("  [OK] vcpkg engine is successfully compiled and active.")

        # Proceed to run installations safely now that vcpkg_exe guaranteed to exist
        print("\n━━━━━━━ Installing vcpkg packages ━━━━━━━")
        for p in pkgs:
            name = p["name"]
            triplet = p.get("triplet", "x64-windows")
            spec = f"{name}:{triplet}"
            print(f"  Installing {spec}...")
            subprocess.run([vcpkg_exe, "install", spec], shell=True)

    # 2. INSTALL PIP PACKAGES
    pip_pkgs = data.get("pip", [])
    if pip_pkgs:
        print("\n━━━━━━━ Installing pip packages ━━━━━━━")
        specs = [
            f"{p['name']}=={p['version']}" if p.get('version') and p['version'] != "latest"
            else p['name']
            for p in pip_pkgs
        ]
        print(f"  Installing: {' '.join(specs)}")
        subprocess.run([sys.executable, "-m", "pip", "install"] + specs, check=True, shell=True)

    # 3. CONFIGURE SOURCE BUILDS
    deps = data.get("source", [])
    if deps:
        refresh_windows_path()
        print("\n━━━━━━━ Executing Source Builds ━━━━━━━")
        cpu_count = str(os.cpu_count() or 4)
        
        for dep in deps:
            name = dep["name"]
            tag = dep["tag"]
            stamp = source_cache / f".{name}-{tag}.stamp"

            if stamp.exists():
                print(f"  [SKIP] {name}@{tag} already installed.")
                continue

            print(f"\n  [BUILD] {name}@{tag}")
            src_dir = source_cache / name
            if not src_dir.exists():
                subprocess.run([
                    "git", "clone", "--depth=1", "--branch", tag,
                    dep["repo"], str(src_dir)
                ], check=True, shell=True)

            build_root = src_dir / (dep.get("build_dir") or "")
            build_dir = src_dir / "_build"
            build_dir.mkdir(exist_ok=True)

            cmake_extra = shlex.split(dep.get("cmake_args") or "")
            try:
                # Dynamic CMake setup
                cmake_args = [
                    "cmake", "-S", str(build_root), "-B", str(build_dir),
                    "-G", "Visual Studio 17 2022", "-A", "x64",
                    "-DCMAKE_BUILD_TYPE=Release",
                    f"-DCMAKE_INSTALL_PREFIX={install_prefix}",
                ]

                # Bind toolchain to our freshly ensured vcpkg root folder
                vcpkg_toolchain = os.path.join(vcpkg_root, "scripts", "buildsystems", "vcpkg.cmake")
                if os.path.exists(vcpkg_toolchain):
                    cmake_args.append(f"-DCMAKE_TOOLCHAIN_FILE={vcpkg_toolchain}")
                    print(f"  [SYSTEM] Successfully linked vcpkg dependency toolchain file.")
                else:
                    print(f"  [WARN] vcpkg toolchain not found at {vcpkg_toolchain}. Proceeding standalone.")

                cmake_args += cmake_extra
                subprocess.run(cmake_args, check=True, shell=True)

            except subprocess.CalledProcessError as e:
                log_file = build_dir / "CMakeFiles" / "CMakeError.log"
                out_file = build_dir / "CMakeFiles" / "CMakeOutput.log"
                print("\n[CRITICAL] CMake configuration failed! Printing internal diagnostics:")
                if log_file.exists():
                    print(f"--- {log_file.name} ---")
                    print(log_file.read_text(errors='ignore')[-2000:]) 
                if out_file.exists():
                    print(f"--- {out_file.name} ---")
                    print(log_file.read_text(errors='ignore')[-1000:])
                raise e 

            # Build phase
            subprocess.run([
                "cmake", "--build", str(build_dir),
                "--config", "Release",
                "--parallel", cpu_count
            ], check=True, shell=True)

            # Target installation phase
            subprocess.run([
                "cmake", "--install", str(build_dir), "--config", "Release"
            ], check=True, shell=True)

            post = dep.get("post_install", "").strip()
            if post:
                print(f"  [POST] {post}")
                subprocess.run(post, shell=True, check=True)

            stamp.touch()
            print(f"  [OK] {name} installed to {install_prefix}")

if __name__ == "__main__":
    main()