#!/usr/bin/env bash
# Install the LocalLLM CLI into a venv and expose `llm` on PATH.
# Run inside WSL2 from the repo root.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

# Where the CLI venv lives. Honors $LLM_DATA_ROOT or falls back to ~/llm.
data_root="${LLM_DATA_ROOT:-$HOME/llm}"
venv_dir="$data_root/.cli-venv"

echo "==> Creating venv at $venv_dir"
mkdir -p "$data_root"
"$PYTHON" -m venv "$venv_dir"

echo "==> Installing localllm-cli (editable)"
"$venv_dir/bin/pip" install --upgrade pip
"$venv_dir/bin/pip" install -e "$REPO_ROOT"

local_bin="$HOME/.local/bin"
mkdir -p "$local_bin"
ln -sf "$venv_dir/bin/llm" "$local_bin/llm"

config_path="${XDG_CONFIG_HOME:-$HOME/.config}/llm/config.yaml"
if [ -z "${LLM_SKIP_SETUP:-}" ] && [ ! -f "$config_path" ]; then
  echo
  echo "==> Running first-time setup"
  ( cd "$REPO_ROOT" && "$venv_dir/bin/llm" setup )
fi

echo
echo "Installed. Make sure ~/.local/bin is on your PATH:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo
echo "Next steps:"
echo "  llm settings show   # confirm settings"
echo "  llm doctor          # verify external prerequisites"
echo "  llm list            # list runtimes, models, configs, benchmarks"
