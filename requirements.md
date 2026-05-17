# External Requirements

<!-- AUTO-GENERATED from requirements.yaml — do not edit by hand. Run `llm doctor render-requirements` to regenerate. -->

These prerequisites must exist on the machine for the LocalLLM CLI and the runtimes' build/serve scripts to function. Run `llm doctor` to verify the current state of each.

## Universal

| ID | Name | Min | Verify | Install | Why |
|---|---|---|---|---|---|
| cuda-driver | NVIDIA CUDA Driver (Windows host) | 535.0 | `nvidia-smi` | https://www.nvidia.com/Download/index.aspx | GPU passthrough into WSL2 |
| python | Python | 3.11 | `python3 --version` | apt install python3.11 python3.11-venv | Base interpreter for runtime venvs and the CLI |
| hf-cli | huggingface-hub CLI | 0.20.0 | `huggingface-cli --version` | pip install -U huggingface_hub[cli] | Used by models/*/pull.sh to fetch weights |
| build-essential | build-essential + cmake | 11.0 | `gcc --version` | apt install build-essential cmake | Building llama.cpp and similar native runtimes |
| git | Git | 2.30 | `git --version` | apt install git | Cloning runtime forks in runtimes/*/build.sh |
| curl | curl | 7.80 | `curl --version` | apt install curl | healthcheck.sh and ad-hoc endpoint probing |
| jq | jq | 1.6 | `jq --version` | apt install jq | JSON parsing in shell scripts |

## Runtime: llamacpp

| ID | Name | Min | Verify | Install | Why |
|---|---|---|---|---|---|
| cmake | cmake | 3.16 | `cmake --version` | apt install cmake | required by llamacpp |
| nvcc | nvcc | 12.0 | `nvcc --version` | Install CUDA toolkit; see NVIDIA docs. | required by llamacpp |
