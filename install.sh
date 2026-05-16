#!/usr/bin/env bash
# Install the LocalLLM CLI into a venv and expose `llm` on PATH.
# Run inside WSL2 from the repo root.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

# Read data_root from paths.yaml (very simple parser — assumes the canonical layout).
data_root_raw=$(awk -F': *' '/^data_root:/ {print $2; exit}' "$REPO_ROOT/paths.yaml")
data_root="${data_root_raw/#\~/$HOME}"
venv_dir="$data_root/.cli-venv"

echo "==> Creating venv at $venv_dir"
mkdir -p "$data_root"
"$PYTHON" -m venv "$venv_dir"

echo "==> Installing localllm-cli (editable) and dependencies"
"$venv_dir/bin/pip" install --upgrade pip
"$venv_dir/bin/pip" install -e "$REPO_ROOT"

local_bin="$HOME/.local/bin"
mkdir -p "$local_bin"
ln -sf "$venv_dir/bin/llm" "$local_bin/llm"

echo
echo "Installed. Make sure ~/.local/bin is on your PATH:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo
echo "Next steps:"
echo "  llm init                    # create data-root subdirectories"
echo "  llm specs                   # generate specs.md"
echo "  llm doctor                  # verify requirements"
