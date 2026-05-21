#!/usr/bin/env bash
# Run llama-server in the foreground.
set -euo pipefail

# shellcheck source=_serve_flags.sh
source "$(dirname "${BASH_SOURCE[0]}")/_serve_flags.sh"

: "${LLM_RUNTIMES:?LLM_RUNTIMES must be set}"
: "${LLM_LLAMACPP_GGUF:?LLM_LLAMACPP_GGUF must be set}"
: "${LLM_SERVE_HOST:?LLM_SERVE_HOST must be set}"
: "${LLM_SERVE_PORT:?LLM_SERVE_PORT must be set}"

BIN="${LLM_RUNTIMES}/llamacpp/llama.cpp/build/bin/llama-server"
if [[ ! -x "${BIN}" ]]; then
  echo "error: llama-server not found at ${BIN}; run loco runtime install llamacpp" >&2
  exit 1
fi

ARGS=(
  "${BIN}"
  --model "${LLM_LLAMACPP_GGUF}"
  --host "${LLM_SERVE_HOST}"
  --port "${LLM_SERVE_PORT}"
)

# Common params
append_arg_if_set ARGS LLM_LLAMACPP_N_GPU_LAYERS --n-gpu-layers
append_arg_if_set ARGS LLM_LLAMACPP_CTX --ctx-size
append_arg_if_set ARGS LLM_LLAMACPP_BATCH_SIZE --batch-size
append_arg_if_set ARGS LLM_LLAMACPP_UBATCH_SIZE --ubatch-size
append_arg_if_set ARGS LLM_LLAMACPP_THREADS --threads
append_arg_if_set ARGS LLM_LLAMACPP_THREADS_BATCH --threads-batch
append_arg_if_set ARGS LLM_LLAMACPP_PARALLEL --parallel
if _is_truthy "${LLM_LLAMACPP_FLASH_ATTN:-false}"; then
  ARGS+=(--flash-attn on)
fi
append_arg_if_set ARGS LLM_LLAMACPP_SPLIT_MODE --split-mode
append_arg_if_set ARGS LLM_LLAMACPP_TENSOR_SPLIT --tensor-split
append_arg_if_set ARGS LLM_LLAMACPP_ROPE_FREQ_BASE --rope-freq-base 1
append_arg_if_set ARGS LLM_LLAMACPP_ROPE_FREQ_SCALE --rope-freq-scale 1
if _is_truthy "${LLM_LLAMACPP_CONT_BATCHING:-true}"; then
  ARGS+=(--cont-batching)
else
  ARGS+=(--no-cont-batching)
fi

# Advanced params
append_arg_if_set ARGS LLM_LLAMACPP_KEEP --keep 1
append_arg_if_set ARGS LLM_LLAMACPP_PREDICT --n-predict
append_bool_if_true ARGS LLM_LLAMACPP_SWA_FULL --swa-full
append_arg_if_set ARGS LLM_LLAMACPP_CTX_CHECKPOINTS --ctx-checkpoints 1
append_arg_if_set ARGS LLM_LLAMACPP_CHECKPOINT_EVERY_N_TOKENS --checkpoint-every-n-tokens
append_arg_if_set ARGS LLM_LLAMACPP_CACHE_RAM --cache-ram 1
if _is_truthy "${LLM_LLAMACPP_KV_UNIFIED:-false}"; then
  ARGS+=(--kv-unified)
fi
if _is_truthy "${LLM_LLAMACPP_CACHE_IDLE_SLOTS:-false}"; then
  ARGS+=(--cache-idle-slots)
fi
if _is_truthy "${LLM_LLAMACPP_CONTEXT_SHIFT:-true}"; then
  ARGS+=(--context-shift)
else
  ARGS+=(--no-context-shift)
fi
append_arg_if_set ARGS LLM_LLAMACPP_CHUNKS --chunks 1
append_arg_if_set ARGS LLM_LLAMACPP_CPU_MASK --cpu-mask
append_arg_if_set ARGS LLM_LLAMACPP_CPU_RANGE --cpu-range
if _is_truthy "${LLM_LLAMACPP_CPU_STRICT:-false}"; then
  ARGS+=(--cpu-strict 1)
fi
append_arg_if_set ARGS LLM_LLAMACPP_PRIO --prio 1
append_arg_if_set ARGS LLM_LLAMACPP_POLL --poll 1
append_arg_if_set ARGS LLM_LLAMACPP_CPU_MASK_BATCH --cpu-mask-batch
append_arg_if_set ARGS LLM_LLAMACPP_CPU_RANGE_BATCH --cpu-range-batch
if _is_truthy "${LLM_LLAMACPP_CPU_STRICT_BATCH:-false}"; then
  ARGS+=(--cpu-strict-batch 1)
fi
append_arg_if_set ARGS LLM_LLAMACPP_PRIO_BATCH --prio-batch 1
append_arg_if_set ARGS LLM_LLAMACPP_POLL_BATCH --poll-batch 1
append_bool_if_true ARGS LLM_LLAMACPP_MLOCK --mlock
append_bool_if_true ARGS LLM_LLAMACPP_NO_MMAP --no-mmap
append_arg_if_set ARGS LLM_LLAMACPP_NUMA --numa
append_arg_if_set ARGS LLM_LLAMACPP_DEVICE --device
append_arg_if_set ARGS LLM_LLAMACPP_OVERRIDE_TENSOR --override-tensor
append_arg_if_set ARGS LLM_LLAMACPP_MAIN_GPU --main-gpu 1
append_arg_if_set ARGS LLM_LLAMACPP_FIT --fit
append_arg_if_set ARGS LLM_LLAMACPP_FIT_PRINT --fit-print
append_arg_if_set ARGS LLM_LLAMACPP_FIT_TARGET --fit-target
append_arg_if_set ARGS LLM_LLAMACPP_FIT_CTX --fit-ctx 1
append_bool_if_true ARGS LLM_LLAMACPP_CHECK_TENSORS --check-tensors
append_arg_if_set ARGS LLM_LLAMACPP_OVERRIDE_KV --override-kv
append_bool_if_true ARGS LLM_LLAMACPP_NO_OP_OFFLOAD --no-op-offload
append_bool_if_true ARGS LLM_LLAMACPP_NO_KV_OFFLOAD --no-kv-offload
append_arg_if_set ARGS LLM_LLAMACPP_CACHE_TYPE_K --cache-type-k
append_arg_if_set ARGS LLM_LLAMACPP_CACHE_TYPE_V --cache-type-v
append_arg_if_set ARGS LLM_LLAMACPP_DEFRAG_THRESHOLD --defrag-thold 1
append_arg_if_set ARGS LLM_LLAMACPP_POOLING --pooling
append_arg_if_set ARGS LLM_LLAMACPP_ATTENTION --attention
append_arg_if_set ARGS LLM_LLAMACPP_ROPE_SCALING --rope-scaling
append_arg_if_set ARGS LLM_LLAMACPP_YARN_ORIG_CTX --yarn-orig-ctx 1
append_arg_if_set ARGS LLM_LLAMACPP_YARN_EXT_FACTOR --yarn-ext-factor 1
append_arg_if_set ARGS LLM_LLAMACPP_YARN_ATTN_FACTOR --yarn-attn-factor 1
append_arg_if_set ARGS LLM_LLAMACPP_YARN_BETA_SLOW --yarn-beta-slow 1
append_arg_if_set ARGS LLM_LLAMACPP_YARN_BETA_FAST --yarn-beta-fast 1
append_arg_if_set ARGS LLM_LLAMACPP_GRP_ATTN_N --grp-attn-n 1
append_arg_if_set ARGS LLM_LLAMACPP_GRP_ATTN_W --grp-attn-w 1
append_arg_if_set ARGS LLM_LLAMACPP_EMBD_NORMALIZE --embd-normalize
append_bool_if_true ARGS LLM_LLAMACPP_EMBEDDING --embedding
append_bool_if_true ARGS LLM_LLAMACPP_RERANKING --reranking
append_arg_if_set ARGS LLM_LLAMACPP_API_KEY --api-key
append_arg_if_set ARGS LLM_LLAMACPP_API_KEY_FILE --api-key-file
append_arg_if_set ARGS LLM_LLAMACPP_SSL_KEY_FILE --ssl-key-file
append_arg_if_set ARGS LLM_LLAMACPP_SSL_CERT_FILE --ssl-cert-file
append_arg_if_set ARGS LLM_LLAMACPP_THREADS_HTTP --threads-http
if _is_truthy "${LLM_LLAMACPP_CACHE_PROMPT:-true}"; then
  ARGS+=(--cache-prompt)
else
  ARGS+=(--no-cache-prompt)
fi
append_arg_if_set ARGS LLM_LLAMACPP_CACHE_REUSE --cache-reuse 1
append_bool_if_true ARGS LLM_LLAMACPP_METRICS --metrics
append_bool_if_true ARGS LLM_LLAMACPP_PROPS --props
if _is_truthy "${LLM_LLAMACPP_SLOTS:-false}"; then
  ARGS+=(--slots)
fi
append_arg_if_set ARGS LLM_LLAMACPP_SLOT_SAVE_PATH --slot-save-path
append_arg_if_set ARGS LLM_LLAMACPP_MEDIA_PATH --media-path
append_arg_if_set ARGS LLM_LLAMACPP_MODELS_DIR --models-dir
append_arg_if_set ARGS LLM_LLAMACPP_MODELS_PRESET --models-preset
append_arg_if_set ARGS LLM_LLAMACPP_MODELS_MAX --models-max 1
if _is_truthy "${LLM_LLAMACPP_MODELS_AUTOLOAD:-false}"; then
  ARGS+=(--models-autoload)
fi
if _is_truthy "${LLM_LLAMACPP_JINJA:-false}"; then
  ARGS+=(--jinja)
fi
append_arg_if_set ARGS LLM_LLAMACPP_REASONING_FORMAT --reasoning-format
append_arg_if_set ARGS LLM_LLAMACPP_REASONING --reasoning
append_arg_if_set ARGS LLM_LLAMACPP_REASONING_BUDGET --reasoning-budget
append_arg_if_set ARGS LLM_LLAMACPP_REASONING_BUDGET_MESSAGE --reasoning-budget-message
append_arg_if_set ARGS LLM_LLAMACPP_CHAT_TEMPLATE --chat-template
append_arg_if_set ARGS LLM_LLAMACPP_CHAT_TEMPLATE_FILE --chat-template-file
append_arg_if_set ARGS LLM_LLAMACPP_CHAT_TEMPLATE_KWARGS --chat-template-kwargs
append_bool_if_true ARGS LLM_LLAMACPP_SKIP_CHAT_PARSING --skip-chat-parsing
append_bool_if_true ARGS LLM_LLAMACPP_PREFILL_ASSISTANT --prefill-assistant
append_arg_if_set ARGS LLM_LLAMACPP_SLOT_PROMPT_SIMILARITY --slot-prompt-similarity 1
append_arg_if_set ARGS LLM_LLAMACPP_LORA --lora
append_arg_if_set ARGS LLM_LLAMACPP_LORA_SCALED --lora-scaled
append_bool_if_true ARGS LLM_LLAMACPP_LORA_INIT_WITHOUT_APPLY --lora-init-without-apply
append_arg_if_set ARGS LLM_LLAMACPP_TIMEOUT --timeout 1
append_arg_if_set ARGS LLM_LLAMACPP_SLEEP_IDLE_SECONDS --sleep-idle-seconds
append_bool_if_true ARGS LLM_LLAMACPP_REUSE_PORT --reuse-port
append_arg_if_set ARGS LLM_LLAMACPP_PATH --path
append_arg_if_set ARGS LLM_LLAMACPP_API_PREFIX --api-prefix
if _is_truthy "${LLM_LLAMACPP_UI:-false}"; then
  ARGS+=(--ui)
fi
append_arg_if_set ARGS LLM_LLAMACPP_UI_CONFIG --ui-config
append_arg_if_set ARGS LLM_LLAMACPP_UI_CONFIG_FILE --ui-config-file
if _is_truthy "${LLM_LLAMACPP_UI_MCP_PROXY:-false}"; then
  ARGS+=(--ui-mcp-proxy)
fi
append_arg_if_set ARGS LLM_LLAMACPP_TOOLS --tools
append_arg_if_set ARGS LLM_LLAMACPP_MODEL_ALIAS --alias
append_arg_if_set ARGS LLM_LLAMACPP_TAGS --tags

# Intentionally word-split extra args for pass-through use.
# shellcheck disable=SC2086
exec "${ARGS[@]}" ${LLM_LLAMACPP_EXTRA_ARGS:-}
