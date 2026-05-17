#!/usr/bin/env bash
set -euo pipefail

: "${LLM_RUNTIMES:?LLM_RUNTIMES must be set (eval \"\$(llm settings env)\")}"

ROOT="${LLM_RUNTIMES}/llamacpp"
SRC="${ROOT}/llama.cpp"
BUILD="${SRC}/build"

mkdir -p "${ROOT}"

if [[ ! -d "${SRC}/.git" ]]; then
  git clone --depth 1 https://github.com/ggerganov/llama.cpp.git "${SRC}"
fi

git -C "${SRC}" submodule update --init --recursive

FLAVOR="${LLM_BUILD_FLAVOR:-cuda}"
JOBS="${LLM_BUILD_JOBS:-0}"
if [[ "${JOBS}" -le 0 ]]; then
  JOBS="$(nproc 2>/dev/null || echo 4)"
fi

CMAKE_FLAGS=()
case "${FLAVOR}" in
  cuda)   CMAKE_FLAGS+=(-DGGML_CUDA=ON) ;;
  vulkan) CMAKE_FLAGS+=(-DGGML_VULKAN=ON) ;;
  cpu)    : ;;
  *) echo "error: unknown flavor ${FLAVOR}" >&2; exit 2 ;;
esac

cmake -S "${SRC}" -B "${BUILD}" -DCMAKE_BUILD_TYPE=Release "${CMAKE_FLAGS[@]}"
cmake --build "${BUILD}" --config Release -j"${JOBS}"

test -x "${BUILD}/bin/llama-server"
echo "llamacpp build: ok (flavor=${FLAVOR}, jobs=${JOBS})"
