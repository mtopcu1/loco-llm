#!/usr/bin/env bash
set -euo pipefail
: "${LLM_DATA_ROOT:?LLM_DATA_ROOT must be set (run loco setup; or eval \"\$(loco settings env)\")}"
mkdir -p "${LLM_DATA_ROOT}/runtimes/stub-runtime"
touch "${LLM_DATA_ROOT}/runtimes/stub-runtime/.built-stub"
echo "stub-runtime build: ok"
