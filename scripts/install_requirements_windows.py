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

    # 1. INSTALL VCPKG PACKAGES
    vcpkg_root = os.environ.get("VCPKG_ROOT", r"C:\orthotech_dev\vcpkg")
    vcpkg_exe = os.path.join(vcpkg_root, "vcpkg.exe")
    pkgs = data.get("vcpkg", [])
    if pkgs and os.path.exists(vcpkg_exe):
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
        
        custom_env = os.environ.copy()
        if os.path.exists(r"C:\BuildTools"):
            custom_env["VS2022INSTALLDIR"] = "C:\\BuildTools\\"
            msvc_bin = "C:\\BuildTools\\VC\\Tools\\MSVC\\14.43.34808\\bin\\Hostx64\\x64"

            if not os.path.exists(msvc_bin):
                import glob
                found = glob.glob("C:\\BuildTools\\VC\\Tools\\MSVC\\*\\bin\\Hostx64\\x64")
                if found: msvc_bin = found[0]

            custom_env["PATH"] = rf"C:\BuildTools\Common7\IDE;{custom_env.get('PATH', '')}"
        
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
                subprocess.run([
                    "cmake", "-S", str(build_root), "-B", str(build_dir),
                    "-G", "Ninja",
                    "-DCMAKE_BUILD_TYPE=Release",
                    f"-DCMAKE_INSTALL_PREFIX={install_prefix}",
                ] + cmake_extra, check=True, shell=True, env=custom_env)
            except subprocess.CalledProcessError as e:
                log_file = build_dir / "CMakeFiles" / "CMakeError.log"
                out_file = build_dir / "CMakeFiles" / "CMakeOutput.log"
                print("\n[CRITICAL] CMake configuration failed! Printing internal diagnostics:")
                if log_file.exists():
                    print(f"--- {log_file.name} ---")
                    print(log_file.read_text(errors='ignore')[-2000:]) 
                if out_file.exists():
                    print(f"--- {out_file.name} ---")
                    print(out_file.read_text(errors='ignore')[-1000:])
                raise e 

            subprocess.run([
                "cmake", "--build", str(build_dir),
                "--config", "Release",
                "--parallel", cpu_count
            ], check=True, shell=True, env=custom_env)

            subprocess.run([
                "cmake", "--install", str(build_dir), "--config", "Release"
            ], check=True, shell=True, env=custom_env)

            post = dep.get("post_install", "").strip()
            if post:
                print(f"  [POST] {post}")
                subprocess.run(post, shell=True, check=True, env=custom_env)

            stamp.touch()
            print(f"  [OK] {name} installed to {install_prefix}")

if __name__ == "__main__":
    main()