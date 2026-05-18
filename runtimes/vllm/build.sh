#!/usr/bin/env bash
set -euo pipefail

: "${LLM_RUNTIMES:?LLM_RUNTIMES must be set (eval \"\$(llm settings env)\")}"

ROOT="${LLM_RUNTIMES}/vllm"
VENV="${ROOT}/venv"

VLLM_VERSION="${LLM_BUILD_VLLM_VERSION:-0.8.5}"
PIP_EXTRA="${LLM_BUILD_PIP_EXTRA:-none}"
EXTRA_PIP_PACKAGES="${LLM_BUILD_EXTRA_PIP_PACKAGES:-}"
FORCE_REINSTALL="${LLM_BUILD_FORCE_REINSTALL:-false}"

mkdir -p "${ROOT}"
python3 -m venv "${VENV}"

# shellcheck disable=SC1091
source "${VENV}/bin/activate"
python -m pip install --upgrade pip setuptools wheel

is_truthy() {
  case "${1,,}" in
    true|1|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

INSTALL_ARGS=()
if is_truthy "${FORCE_REINSTALL}"; then
  INSTALL_ARGS+=(--force-reinstall)
fi

case "${PIP_EXTRA}" in
  cuda)
    INSTALL_ARGS+=(--extra-index-url "https://download.pytorch.org/whl/cu124")
    ;;
  cpu)
    INSTALL_ARGS+=(--extra-index-url "https://download.pytorch.org/whl/cpu")
    ;;
  none)
    ;;
  *)
    echo "error: unsupported LLM_BUILD_PIP_EXTRA=${PIP_EXTRA}" >&2
    exit 2
    ;;
esac

python -m pip install "${INSTALL_ARGS[@]}" "vllm==${VLLM_VERSION}"

if [[ -n "${EXTRA_PIP_PACKAGES}" ]]; then
  # Intentionally split to allow multiple packages in one field.
  # shellcheck disable=SC2086
  python -m pip install "${INSTALL_ARGS[@]}" ${EXTRA_PIP_PACKAGES}
fi

vllm --version
echo "vllm build: ok (version=${VLLM_VERSION}, pip_extra=${PIP_EXTRA})"
