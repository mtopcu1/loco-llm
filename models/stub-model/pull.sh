#!/usr/bin/env bash
set -euo pipefail
: "${LLM_MODELS:?LLM_MODELS must be set (run llm init; source .llm-env)}"
mkdir -p "${LLM_MODELS}/stub-model"
echo "stub weights placeholder" > "${LLM_MODELS}/stub-model/README.txt"
echo "stub-model pull: ok"
