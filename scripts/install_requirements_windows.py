#!/usr/bin/env python3
import os
import sys
import json
import shlex
import subprocess
from pathlib import Path

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
            subprocess.run([vcpkg_exe, "install", spec])

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
        subprocess.run([sys.executable, "-m", "pip", "install"] + specs, check=True)

    # 3. CONFIGURE SOURCE BUILDS
    deps = data.get("source", [])
    if deps:
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
            subprocess.run([
                "cmake", "-S", str(build_root), "-B", str(build_dir),
                "-DCMAKE_BUILD_TYPE=Release",
                f"-DCMAKE_INSTALL_PREFIX={install_prefix}",
            ] + cmake_extra, check=True)

            subprocess.run([
                "cmake", "--build", str(build_dir),
                "--config", "Release",
                "--parallel", cpu_count
            ], check=True)

            subprocess.run([
                "cmake", "--install", str(build_dir), "--config", "Release"
            ], check=True)

            post = dep.get("post_install", "").strip()
            if post:
                print(f"  [POST] {post}")
                subprocess.run(post, shell=True, check=True)

            stamp.touch()
            print(f"  [OK] {name} installed to {install_prefix}")

if __name__ == "__main__":
    main()