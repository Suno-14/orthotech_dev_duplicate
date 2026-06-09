from pathlib import Path
import yaml


def main():
    repo_root = Path(__file__).resolve().parent.parent

    config_file = repo_root / "config" / "dependencies.yml"

    with open(config_file, "r", encoding="utf-8") as file:
        cfg = yaml.safe_load(file)

    outputs = cfg["outputs"]

    for platform in ["linux", "windows"]:
        requirements = []

        # Common packages
        for package in cfg["dependencies"]["common"]["packages"]:
            requirements.append(f"package:{package}")

        # Platform packages
        for package in cfg["dependencies"][platform].get("packages", []):
            requirements.append(f"package:{package}")

        # Source dependencies
        for dependency in cfg["dependencies"][platform].get("source", []):
            requirements.append(f"source:{dependency}")

        # vcpkg dependencies
        for dependency in cfg["dependencies"][platform].get("vcpkg", []):
            requirements.append(f"vcpkg:{dependency}")

        output_file = repo_root / outputs[platform]

        with open(output_file, "w", encoding="utf-8") as file:
            file.write("\n".join(requirements))
            file.write("\n")

        print(f"Generated: {output_file}")


if __name__ == "__main__":
    main()
