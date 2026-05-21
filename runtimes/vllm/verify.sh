#!/usr/bin/env bash
set -euo pipefail

: "${LLM_RUNTIMES:?LLM_RUNTIMES must be set}"
VENV="${LLM_RUNTIMES}/vllm/venv"
if [[ ! -f "${VENV}/bin/activate" ]]; then
  echo "error: missing venv at ${VENV}; run loco runtime install vllm" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"
vloco --version
