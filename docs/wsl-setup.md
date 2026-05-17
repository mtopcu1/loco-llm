# WSL2 Setup

One-time host/WSL setup for running the LocalLLM CLI and (later) actual runtimes.

## Prerequisites

- Windows 10 22H2+ or Windows 11
- An NVIDIA GPU
- Admin access on the host

## Steps

### 1. Install / update WSL2

In an elevated PowerShell:

```powershell
wsl --install -d Ubuntu-22.04   # if WSL not yet installed
wsl --update                    # ensure recent enough for systemd support
wsl --version                   # confirm WSL version >= 2.0
```

### 2. Install the NVIDIA driver on the host

Install the latest **Game Ready** or **Studio** driver for your GPU from
https://www.nvidia.com/Download/index.aspx. The host driver provides the
GPU passthrough into WSL2 — **do not** install a CUDA driver inside WSL.

Verify from WSL after rebooting:

```bash
nvidia-smi
```

You should see your GPU(s) listed with a driver version.

### 3. Enable systemd in WSL

Edit `/etc/wsl.conf` (create if missing):

```ini
[boot]
systemd=true
```

From PowerShell:

```powershell
wsl --shutdown
```

Re-open WSL, then verify:

```bash
systemctl is-system-running    # 'running' or 'degraded' is fine
```

If you plan to use **`llm serve --systemd`**, enable **user lingering** so the service survives closing all interactive sessions when systemd is your session manager:

```bash
loginctl show-user --property=Linger   # want Linger=yes
# if you see Linger=no:
sudo loginctl enable-linger "$USER"
```

`llm doctor` prints an advisory when it detects `Linger=no`.

### 4. Tune WSL memory and swap (optional but recommended)

Edit `~/.wslconfig` on the **Windows** host (for example `C:\Users\you\.wslconfig`):

```ini
[wsl2]
memory=48GB        # cap WSL's total RAM
swap=16GB
```

Adjust based on your physical RAM. Run `wsl --shutdown` to apply.

### 5. Install Python 3.11+, build tools, hf CLI

Inside WSL:

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv build-essential cmake git curl jq
pip install -U huggingface_hub[cli]
```

### 6. Bootstrap the LocalLLM CLI

```bash
cd /mnt/c/Private/Projects/LocalLLM   # or wherever the repo lives
./install.sh
export PATH="$HOME/.local/bin:$PATH"
llm setup
llm specs
llm doctor
```

`llm doctor` should report all requirements as OK. If something is missing or outdated, the doctor's output includes the install hint.

## Common pitfalls

- **`nvidia-smi: command not found` inside WSL** — you installed the driver inside WSL or used an old driver. Uninstall any in-WSL CUDA driver and install the latest host driver from NVIDIA.
- **Models stored on `/mnt/c/...`** — very slow for weight loading. Always store under `~/llm/` (WSL ext4) or a dedicated mounted Linux drive.
- **`systemctl is-system-running` returns `offline`** — `/etc/wsl.conf` change did not take. Confirm the file content, then `wsl --shutdown` and re-open.
- **`llm` not on PATH** — add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc`.
