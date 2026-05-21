# External Requirements

<!-- AUTO-GENERATED from requirements.yaml — do not edit by hand. Run `loco doctor render-requirements` to regenerate. -->

These prerequisites must exist on the machine for the LocalLLM CLI and the runtimes' build/serve scripts to function. Run `loco doctor` to verify the current state of each.

## Universal

| ID | Name | Min | Verify | Install | Why |
|---|---|---|---|---|---|
| cuda-driver | NVIDIA CUDA Driver (Windows host) | 535.0 | `nvidia-smi` | Install the NVIDIA GPU driver on Windows (WSL2 uses the host driver).
https://www.nvidia.com/Download/index.aspx
 | GPU passthrough into WSL2 |
| python | Python | 3.11 | `python3 --version` | https://www.python.org/downloads/ (3.11+)
Debian/Ubuntu: sudo apt install python3.11 python3.11-venv
macOS: brew install python@3.11
 | Base interpreter for runtime venvs and the CLI |
| hf-cli | huggingface-hub CLI | 0.20.0 | `hf --version` | pip install -U "huggingface_hub[cli]"
https://huggingface.co/docs/huggingface_hub/en/guides/cli
 | Used by models/*/pull.sh to fetch weights |
| build-essential | C/C++ toolchain (gcc, g++) | 11.0 | `gcc --version` | Debian/Ubuntu: sudo apt install build-essential
Fedora: sudo dnf groupinstall "Development Tools"
macOS: xcode-select --install
https://gcc.gnu.org/install/
 | Building llama.cpp and similar native runtimes |
| git | Git | 2.30 | `git --version` | https://git-scm.com/downloads
Debian/Ubuntu: sudo apt install git
macOS: brew install git
 | Cloning runtime forks in runtimes/*/build.sh |
| curl | curl | 7.80 | `curl --version` | https://curl.se/download.html
Debian/Ubuntu: sudo apt install curl
macOS: brew install curl
 | healthcheck.sh and ad-hoc endpoint probing |

## Scope: dashboard

| ID | Name | Min | Verify | Install | Why |
|---|---|---|---|---|---|
| node | Node.js | 20.0.0 | `node --version` | https://nodejs.org/ (LTS 20+)
WSL/Linux: https://github.com/nvm-sh/nvm#installing-and-updating
macOS: brew install node
 | loco dashboard install / serve |
| npm | npm | 10.0.0 | `npm --version` | Bundled with Node.js — install Node first (see node hint).
https://docs.npmjs.com/downloading-and-installing-node-js-and-npm
 | loco dashboard install / serve |

## Runtime: llamacpp

| ID | Name | Min | Verify | Install | Why |
|---|---|---|---|---|---|
| cmake | cmake | 3.16 | `cmake --version` | pip install -U "cmake>=3.16"
Debian/Ubuntu: sudo apt install cmake
https://cmake.org/download/
 | required by llamacpp |
