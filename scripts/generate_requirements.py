from pathlib import Path
import yaml
import json                          # ADD THIS


def main():
    repo_root = Path(__file__).resolve().parent.parent
    config_file = repo_root / "config" / "dependencies.yml"

    with open(config_file, "r", encoding="utf-8") as file:
        cfg = yaml.safe_load(file)

    outputs = cfg["outputs"]

    for platform in ["linux", "windows"]:
        requirements = {                 # CHANGE: dict instead of flat list
            "packages": [],
            "source": [],
            "vcpkg": []
        }

        # Common packages
        for package in cfg["dependencies"]["common"]["packages"]:
            requirements["packages"].append(package)   # CHANGE: no "package:" prefix

        # Platform packages
        for package in cfg["dependencies"][platform].get("packages", []):
            requirements["packages"].append(package)   # CHANGE: no "package:" prefix

        # Source dependencies
        for dependency in cfg["dependencies"][platform].get("source", []):
            requirements["source"].append(dependency)  # CHANGE: no "source:" prefix

        # vcpkg dependencies
        for dependency in cfg["dependencies"][platform].get("vcpkg", []):
            requirements["vcpkg"].append(dependency)   # CHANGE: no "vcpkg:" prefix

        output_file = repo_root / outputs[platform]

        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(requirements, file, indent=2)    # CHANGE: json.dump instead of "\n".join
            file.write("\n")

        print(f"Generated: {output_file}")


if __name__ == "__main__":
    main()
