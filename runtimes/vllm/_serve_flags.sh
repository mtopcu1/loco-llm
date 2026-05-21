#!/usr/bin/env bash
# Shared helpers for composing `vloco serve` argv.

_is_truthy() {
  case "${1,,}" in
    true|1|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

# append_arg_if_set ARGS_ARRAY ENV_VAR_NAME CLI_FLAG [omit_zero]
append_arg_if_set() {
  local -n _args_ref="$1"
  local var_name="$2"
  local cli_flag="$3"
  local omit_zero="${4:-0}"
  local val="${!var_name-}"

  if [[ -z "${val}" ]]; then
    return 0
  fi

  if [[ "${omit_zero}" == "1" ]]; then
    case "${val}" in
      0|0.0|0.00|0.000) return 0 ;;
    esac
  fi

  _args_ref+=("${cli_flag}" "${val}")
}

# append_bool_if_true ARGS_ARRAY ENV_VAR_NAME CLI_FLAG
append_bool_if_true() {
  local -n _args_ref="$1"
  local var_name="$2"
  local cli_flag="$3"

  if _is_truthy "${!var_name:-false}"; then
    _args_ref+=("${cli_flag}")
  fi
}
