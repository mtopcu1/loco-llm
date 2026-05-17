#!/usr/bin/env bash
set -euo pipefail
: "${LLM_RUNTIMES:?LLM_RUNTIMES must be set}"
BIN="${LLM_RUNTIMES}/llamacpp/llama.cpp/build/bin/llama-server"
if [[ ! -x "${BIN}" ]]; then
  echo "error: llama-server missing at ${BIN}" >&2
  exit 1
fi
"${BIN}" --version >/dev/null 2>&1 || "${BIN}" --help >/dev/null
