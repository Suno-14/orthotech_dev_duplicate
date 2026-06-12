#!/usr/bin/env python3
"""
generate_requirements.py
========================
Reads config/dependencies.yml and writes:
  generated/linux-requirements.json
  generated/windows-requirements.json

Each JSON has four keys:
  packages  : apt packages  (Linux) or [] (Windows — use vcpkg instead)
  vcpkg     : vcpkg entries (Windows primarily)
  source    : git+cmake source builds
  pip       : Python pip packages

Common entries are merged first; platform entries are appended after.
Duplicate names within the same category are silently deduplicated
(first definition wins).

Usage:
  python config/generate_requirements.py [--validate]
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("[ERROR] pyyaml not installed. Run: pip install pyyaml")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR  = Path(__file__).resolve().parent
REPO_ROOT   = SCRIPT_DIR.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_yaml(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"[ERROR] Not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not data:
        sys.exit(f"[ERROR] Empty or invalid YAML: {path}")
    return data


def normalise_package(entry) -> dict:
    """Accept either a plain string or a dict with at least 'name'."""
    if isinstance(entry, str):
        return {"name": entry}
    if isinstance(entry, dict) and "name" in entry:
        return entry
    sys.exit(f"[ERROR] Invalid package entry (must be string or dict with 'name'): {entry}")


def normalise_vcpkg(entry) -> dict:
    """vcpkg entries must have 'name'; 'triplet' is optional."""
    e = normalise_package(entry)
    e.setdefault("triplet", "x64-windows")
    return e


def normalise_source(entry) -> dict:
    """Source entries must have name + repo + tag."""
    if isinstance(entry, str):
        sys.exit(
            f"[ERROR] Source dep '{entry}' is a bare string — "
            "source entries need at minimum: name, repo, tag."
        )
    required = ("name", "repo", "tag")
    for field in required:
        if field not in entry:
            sys.exit(
                f"[ERROR] Source dep '{entry.get('name', '?')}' is missing '{field}'."
            )
    entry.setdefault("cmake_args", "")
    entry.setdefault("build_dir", "")
    entry.setdefault("post_install", "")
    return entry


def normalise_pip(entry) -> dict:
    e = normalise_package(entry)
    e.setdefault("version", "latest")
    return e


def merge_unique(base: list, extra: list, key: str = "name") -> list:
    """Append extra items to base, skipping duplicates by key."""
    seen = {item[key] for item in base}
    result = list(base)
    for item in extra:
        if item[key] not in seen:
            result.append(item)
            seen.add(item[key])
        else:
            print(f"  [DEDUP] '{item[key]}' already defined — skipping platform override.")
    return result


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
def build_requirements(cfg: dict, platform: str) -> dict:
    deps     = cfg.get("dependencies", {})
    common   = deps.get("common", {})
    plat     = deps.get(platform, {})

    # packages
    common_pkgs = [normalise_package(p) for p in common.get("packages", [])]
    plat_pkgs   = [normalise_package(p) for p in plat.get("packages", [])]
    packages    = merge_unique(common_pkgs, plat_pkgs)

    # vcpkg (Windows mainly; common can define some too)
    common_vcpkg = [normalise_vcpkg(v) for v in common.get("vcpkg", [])]
    plat_vcpkg   = [normalise_vcpkg(v) for v in plat.get("vcpkg", [])]
    vcpkg        = merge_unique(common_vcpkg, plat_vcpkg)

    # source
    common_src = [normalise_source(s) for s in common.get("source", [])]
    plat_src   = [normalise_source(s) for s in plat.get("source", [])]
    source     = merge_unique(common_src, plat_src)

    # pip
    common_pip = [normalise_pip(p) for p in common.get("pip", [])]
    plat_pip   = [normalise_pip(p) for p in plat.get("pip", [])]
    pip        = merge_unique(common_pip, plat_pip)

    return {
        "platform": platform,
        "project":  cfg.get("project", {}),
        "packages": packages,
        "vcpkg":    vcpkg,
        "source":   source,
        "pip":      pip,
    }


def validate(requirements: dict, platform: str):
    errors = []

    for s in requirements["source"]:
        if not s.get("repo"):
            errors.append(f"  [{platform}] source '{s['name']}' has no repo URL.")
        if not s.get("tag"):
            errors.append(f"  [{platform}] source '{s['name']}' has no tag.")

    if errors:
        print(f"[VALIDATE] {len(errors)} issue(s) found:")
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print(f"[VALIDATE] {platform}: OK")


def generate(config_path: Path, validate_flag: bool):
    print(f"[INFO] Reading {config_path}")
    cfg = load_yaml(config_path)

    output_map = cfg.get("outputs", {
        "linux":   "generated/linux-requirements.json",
        "windows": "generated/windows-requirements.json",
    })

    for platform in ("linux", "windows"):
        req = build_requirements(cfg, platform)

        if validate_flag:
            validate(req, platform)

        out_path = REPO_ROOT / output_map[platform]
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(req, fh, indent=2)
            fh.write("\n")

        print(
            f"[OK]  {out_path}  "
            f"(packages={len(req['packages'])}, "
            f"vcpkg={len(req['vcpkg'])}, "
            f"source={len(req['source'])}, "
            f"pip={len(req['pip'])})"
        )

    print("\n[DONE] Requirements generated successfully.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate platform requirements JSON from dependencies.yml"
    )
    parser.add_argument(
        "--config",
        default=str(SCRIPT_DIR / "../config/dependencies.yml"),
        help="Path to dependencies.yml (default: config/dependencies.yml)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate source entries have repo + tag before writing output",
    )
    args = parser.parse_args()
    generate(Path(args.config), args.validate)


if __name__ == "__main__":
    main()
