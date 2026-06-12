# Orthotech Master Development Toolchain

This repository contains the unified, cross-platform build and environment management toolchain for the Orthotech Surgical Robotics Suite. It provides **Single Source of Truth** configuration management, local workstation bootstrapping, and identical environment parity inside automated CI/CD servers.

---

## Architecture Overview

The toolchain operates as a three-stage pipeline to establish identical developer and server environments:

1. **System Prerequisites (`install-prerequisites`)**: Native system setups installing core software compilers, CMake, Ninja, Git, and Python 3.11.
2. **Dynamic Generation (`generate_requirements`)**: Compiles the unified `config/dependencies.yml` configuration blueprint into low-level JSON manifests.
3. **Project Setup (`dev-setup`)**: Clones floating git submodules via branch mappings, provisions package managers (like `vcpkg`), and builds custom source code targets (hardware drivers/math frameworks) using parallel CPU cores.

---

##  Key Configuration Files

* **`config/dependencies.yml`**: The primary blueprint listing all system utilities, packages, `vcpkg` libraries, and source dependencies.
* **`config/submodule_branches.json`**: A tracking matrix mapping every individual git submodule to its target floating branch (e.g., tracking `dev` for active engineering or `main` for stable releases).

---

##  Local Developer Setup (Run Once)

When configuring a fresh developer workstation or onboarding a new engineer, you can run the entire sequence using the master Python helper script.

### On Windows 11
#### 1. One-Time Prerequisites Setup (Admin)
Before running the project for the first time, open **PowerShell as an Administrator** in the root directory and run the initialization script to install Git, CMake, PowerShell Core (`pwsh`), and Python 3.11:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\install-prerequisites.ps1
```
#### 2. Fix the Windows Python Path Conflict
Windows 11 includes pre-installed, empty Python shortcuts (`WindowsApps`) that override your real installation and redirect you to the Microsoft Store. 

To fix this for your current PowerShell session instantly, copy and paste this command:
```powershell
$env:PATH = "$env:USERPROFILE\AppData\Local\Programs\Python\Python311\;$env:USERPROFILE\AppData\Local\Programs\Python\Python311\Scripts\;" + $env:PATH
```
### On Linux (Ubuntu) 

```bash
sudo python3 scripts/setup_all.py
```