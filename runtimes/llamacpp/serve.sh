#!/usr/bin/env bash
# Run llama-server in the foreground. Env comes from `llm serve` / typed serve.params.
set -euo pipefail

: "${LLM_RUNTIMES:?LLM_RUNTIMES must be set}"
: "${LLM_LLAMACPP_GGUF:?LLM_LLAMACPP_GGUF must be set}"
: "${LLM_SERVE_HOST:?LLM_SERVE_HOST must be set}"
: "${LLM_SERVE_PORT:?LLM_SERVE_PORT must be set}"

BIN="${LLM_RUNTIMES}/llamacpp/llama.cpp/build/bin/llama-server"
if [[ ! -x "${BIN}" ]]; then
  echo "error: llama-server not found at ${BIN}; run llm runtime install llamacpp" >&2
  exit 1
fi

NGL="${LLM_LLAMACPP_N_GPU_LAYERS:--1}"
CTX="${LLM_LLAMACPP_CTX:-8192}"

# LLM_LLAMACPP_EXTRA_ARGS is intentionally word-split for extra flags (may be empty).
# shellcheck disable=SC2086
exec "${BIN}" \
  --model "${LLM_LLAMACPP_GGUF}" \
  --host "${LLM_SERVE_HOST}" \
  --port "${LLM_SERVE_PORT}" \
  --n-gpu-layers "${NGL}" \
  --ctx-size "${CTX}" \
  ${LLM_LLAMACPP_EXTRA_ARGS:-}
