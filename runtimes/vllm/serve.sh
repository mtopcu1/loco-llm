#!/usr/bin/env bash
# Run vllm serve in the foreground.
set -euo pipefail

# shellcheck source=_serve_flags.sh
source "$(dirname "${BASH_SOURCE[0]}")/_serve_flags.sh"

: "${LLM_RUNTIMES:?LLM_RUNTIMES must be set}"
: "${LLM_VLLM_MODEL:?LLM_VLLM_MODEL must be set}"
: "${LLM_SERVE_HOST:?LLM_SERVE_HOST must be set}"
: "${LLM_SERVE_PORT:?LLM_SERVE_PORT must be set}"

VENV="${LLM_RUNTIMES}/vllm/venv"
if [[ ! -f "${VENV}/bin/activate" ]]; then
  echo "error: missing venv at ${VENV}; run llm runtime install vllm" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"

VLLM_BIN="$(command -v vllm || true)"
if [[ -z "${VLLM_BIN}" ]]; then
  echo "error: vllm binary not found in ${VENV}" >&2
  exit 1
fi

ARGS=(
  "${VLLM_BIN}"
  serve
  "${LLM_VLLM_MODEL}"
  --host "${LLM_SERVE_HOST}"
  --port "${LLM_SERVE_PORT}"
)

# Common params
append_arg_if_set ARGS LLM_VLLM_DTYPE --dtype
append_arg_if_set ARGS LLM_VLLM_MAX_MODEL_LEN --max-model-len
append_arg_if_set ARGS LLM_VLLM_GPU_MEMORY_UTILIZATION --gpu-memory-utilization
append_arg_if_set ARGS LLM_VLLM_TENSOR_PARALLEL_SIZE --tensor-parallel-size
append_arg_if_set ARGS LLM_VLLM_PIPELINE_PARALLEL_SIZE --pipeline-parallel-size
append_bool_if_true ARGS LLM_VLLM_ENFORCE_EAGER --enforce-eager
append_arg_if_set ARGS LLM_VLLM_SWAP_SPACE --swap-space
append_arg_if_set ARGS LLM_VLLM_MAX_NUM_SEQS --max-num-seqs

# Advanced params
append_arg_if_set ARGS LLM_VLLM_SERVED_MODEL_NAME --served-model-name
append_arg_if_set ARGS LLM_VLLM_TOKENIZER --tokenizer
append_arg_if_set ARGS LLM_VLLM_TOKENIZER_MODE --tokenizer-mode
append_bool_if_true ARGS LLM_VLLM_TRUST_REMOTE_CODE --trust-remote-code
append_arg_if_set ARGS LLM_VLLM_REVISION --revision
append_arg_if_set ARGS LLM_VLLM_CODE_REVISION --code-revision
append_arg_if_set ARGS LLM_VLLM_TOKENIZER_REVISION --tokenizer-revision
append_arg_if_set ARGS LLM_VLLM_DOWNLOAD_DIR --download-dir
append_arg_if_set ARGS LLM_VLLM_LOAD_FORMAT --load-format
append_arg_if_set ARGS LLM_VLLM_QUANTIZATION --quantization
append_arg_if_set ARGS LLM_VLLM_KV_CACHE_DTYPE --kv-cache-dtype
append_arg_if_set ARGS LLM_VLLM_MAX_NUM_BATCHED_TOKENS --max-num-batched-tokens 1
append_arg_if_set ARGS LLM_VLLM_MAX_NUM_PARTIAL_PREFILLS --max-num-partial-prefills 1
append_arg_if_set ARGS LLM_VLLM_MAX_LONG_PARTIAL_PREFILLS --max-long-partial-prefills 1
append_arg_if_set ARGS LLM_VLLM_MAX_SEQ_LEN_TO_CAPTURE --max-seq-len-to-capture
append_arg_if_set ARGS LLM_VLLM_BLOCK_SIZE --block-size
append_arg_if_set ARGS LLM_VLLM_SEED --seed 1
append_arg_if_set ARGS LLM_VLLM_CPU_OFFLOAD_GB --cpu-offload-gb 1
append_arg_if_set ARGS LLM_VLLM_NUM_SCHEDULER_STEPS --num-scheduler-steps
append_arg_if_set ARGS LLM_VLLM_SCHEDULER_DELAY_FACTOR --scheduler-delay-factor 1
append_bool_if_true ARGS LLM_VLLM_ENABLE_PREFIX_CACHING --enable-prefix-caching
append_bool_if_true ARGS LLM_VLLM_DISABLE_SLIDING_WINDOW --disable-sliding-window
append_bool_if_true ARGS LLM_VLLM_DISABLE_CUSTOM_ALL_REDUCE --disable-custom-all-reduce
append_bool_if_true ARGS LLM_VLLM_DISABLE_FRONTEND_MULTIPROCESSING --disable-frontend-multiprocessing
append_bool_if_true ARGS LLM_VLLM_DISABLE_LOG_STATS --disable-log-stats
append_bool_if_true ARGS LLM_VLLM_DISABLE_LOG_REQUESTS --disable-log-requests
append_arg_if_set ARGS LLM_VLLM_MAX_LOG_LEN --max-log-len 1
append_arg_if_set ARGS LLM_VLLM_UVICORN_LOG_LEVEL --uvicorn-log-level
append_bool_if_true ARGS LLM_VLLM_ALLOW_CREDENTIALS --allow-credentials
append_arg_if_set ARGS LLM_VLLM_ALLOWED_ORIGINS --allowed-origins
append_arg_if_set ARGS LLM_VLLM_ALLOWED_METHODS --allowed-methods
append_arg_if_set ARGS LLM_VLLM_ALLOWED_HEADERS --allowed-headers
append_arg_if_set ARGS LLM_VLLM_API_KEY --api-key
append_arg_if_set ARGS LLM_VLLM_CHAT_TEMPLATE --chat-template
append_arg_if_set ARGS LLM_VLLM_CHAT_TEMPLATE_CONTENT_FORMAT --chat-template-content-format
append_arg_if_set ARGS LLM_VLLM_RESPONSE_ROLE --response-role
append_arg_if_set ARGS LLM_VLLM_GUIDED_DECODING_BACKEND --guided-decoding-backend
append_arg_if_set ARGS LLM_VLLM_LIMIT_MM_PER_PROMPT --limit-mm-per-prompt
append_bool_if_true ARGS LLM_VLLM_ENABLE_AUTO_TOOL_CHOICE --enable-auto-tool-choice
append_arg_if_set ARGS LLM_VLLM_TOOL_CALL_PARSER --tool-call-parser
append_arg_if_set ARGS LLM_VLLM_REASONING_PARSER --reasoning-parser
append_bool_if_true ARGS LLM_VLLM_ENABLE_PROMPT_TOKENS_DETAILS --enable-prompt-tokens-details
append_bool_if_true ARGS LLM_VLLM_DISABLE_ASYNC_OUTPUT_PROC --disable-async-output-proc
append_arg_if_set ARGS LLM_VLLM_DATA_PARALLEL_SIZE --data-parallel-size
append_arg_if_set ARGS LLM_VLLM_DISTRIBUTED_EXECUTOR_BACKEND --distributed-executor-backend
append_arg_if_set ARGS LLM_VLLM_MAX_PARALLEL_LOADING_WORKERS --max-parallel-loading-workers 1
append_bool_if_true ARGS LLM_VLLM_USE_TQDM_ON_LOAD --use-tqdm-on-load

# Intentionally word-split extra args for pass-through use.
# shellcheck disable=SC2086
exec "${ARGS[@]}" ${LLM_VLLM_EXTRA_ARGS:-}
