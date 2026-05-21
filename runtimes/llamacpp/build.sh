#!/usr/bin/env bash
set -euo pipefail

: "${LLM_RUNTIMES:?LLM_RUNTIMES must be set (eval \"\$(loco settings env)\")}"

ROOT="${LLM_RUNTIMES}/llamacpp"
SRC="${ROOT}/llama.cpp"
BUILD="${SRC}/build"

mkdir -p "${ROOT}"

git_ref="${LLM_BUILD_GIT_REF:-b9209}"

if [[ ! -d "${SRC}/.git" ]]; then
  git clone --depth 1 --branch "${git_ref}" https://github.com/ggerganov/llama.cpp.git "${SRC}" \
    || {
      git clone https://github.com/ggerganov/llama.cpp.git "${SRC}"
      git -C "${SRC}" fetch --depth 1 origin "refs/tags/${git_ref}:refs/tags/${git_ref}" 2>/dev/null \
        || git -C "${SRC}" fetch --depth 1 origin "${git_ref}"
      git -C "${SRC}" checkout -q "${git_ref}"
    }
else
  git -C "${SRC}" fetch --depth 1 origin "refs/tags/${git_ref}:refs/tags/${git_ref}" 2>/dev/null \
    || git -C "${SRC}" fetch --depth 1 origin "${git_ref}"
  git -C "${SRC}" checkout -q "${git_ref}"
fi

git -C "${SRC}" submodule update --init --recursive

FLAVOR="${LLM_BUILD_FLAVOR:-cuda}"
JOBS="${LLM_BUILD_JOBS:-0}"
if [[ "${JOBS}" -le 0 ]]; then
  JOBS="$(nproc 2>/dev/null || echo 4)"
fi

CMAKE_BUILD_TYPE="${LLM_BUILD_CMAKE_BUILD_TYPE:-Release}"
CUBLAS="${LLM_BUILD_CUBLAS:-true}"
FLASH_ATTN="${LLM_BUILD_FLASH_ATTN:-false}"
NATIVE="${LLM_BUILD_NATIVE:-true}"
CUDA_ARCH="${LLM_BUILD_CUDA_ARCHITECTURES:-}"
STATIC="${LLM_BUILD_STATIC:-false}"
CLEAN_BUILD="${LLM_BUILD_CLEAN_BUILD:-false}"

_is_true() {
  case "${1,,}" in
    true|1|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

if _is_true "${CLEAN_BUILD}"; then
  rm -rf "${BUILD}"
fi

CMAKE_FLAGS=()
case "${FLAVOR}" in
  cuda)   CMAKE_FLAGS+=(-DGGML_CUDA=ON) ;;
  vulkan) CMAKE_FLAGS+=(-DGGML_VULKAN=ON) ;;
  cpu)    : ;;
  *) echo "error: unknown flavor ${FLAVOR}" >&2; exit 2 ;;
esac

if _is_true "${NATIVE}"; then
  CMAKE_FLAGS+=(-DGGML_NATIVE=ON)
else
  CMAKE_FLAGS+=(-DGGML_NATIVE=OFF)
fi

if [[ "${FLAVOR}" == cuda ]]; then
  if _is_true "${CUBLAS}"; then
    CMAKE_FLAGS+=(-DGGML_CUDA_FORCE_MMQ=OFF)
  else
    CMAKE_FLAGS+=(-DGGML_CUDA_FORCE_MMQ=ON)
  fi
  if _is_true "${FLASH_ATTN}"; then
    CMAKE_FLAGS+=(-DGGML_CUDA_FA=ON)
  else
    CMAKE_FLAGS+=(-DGGML_CUDA_FA=OFF)
  fi
  if [[ -n "${CUDA_ARCH}" ]]; then
    CMAKE_FLAGS+=(-DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCH}")
  fi
fi

if _is_true "${STATIC}"; then
  CMAKE_FLAGS+=(-DBUILD_SHARED_LIBS=OFF)
else
  CMAKE_FLAGS+=(-DBUILD_SHARED_LIBS=ON)
fi

cmake -S "${SRC}" -B "${BUILD}" -DCMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE}" "${CMAKE_FLAGS[@]}"
cmake --build "${BUILD}" --config "${CMAKE_BUILD_TYPE}" -j"${JOBS}"

test -x "${BUILD}/bin/llama-server"
echo "llamacpp build: ok (flavor=${FLAVOR}, jobs=${JOBS}, ref=${git_ref})"
