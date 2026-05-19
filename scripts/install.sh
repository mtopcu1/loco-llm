#!/usr/bin/env bash
# Public one-line installer for loco-llm.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
# Options:
#   --dir <path>      override LOCO_LLM_HOME (default: $HOME/.loco-llm)
#   --branch <name>   clone+checkout a branch instead of the latest tag
#   --tag <vX.Y.Z>    pin to a specific tag
set -euo pipefail

REPO_URL="https://github.com/mtopcu1/loco-llm.git"
REMOTE_HOST="github.com/mtopcu1/loco-llm"
LOCO_LLM_HOME="${LOCO_LLM_HOME:-$HOME/.loco-llm}"
PYTHON_MIN="3.11"
REF_BRANCH=""
REF_TAG=""

die() { echo "error: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dir)    LOCO_LLM_HOME="$2"; shift 2 ;;
    --branch) REF_BRANCH="$2"; shift 2 ;;
    --tag)    REF_TAG="$2"; shift 2 ;;
    *)        die "unknown argument: $1" ;;
  esac
done

need git
need curl
python3 - <<PY || die "python3 >= ${PYTHON_MIN} required"
import sys
major, minor = sys.version_info[:2]
raise SystemExit(0 if (major, minor) >= (3, 11) else 1)
PY

if ! command -v uv >/dev/null 2>&1; then
  echo "==> installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if [ -d "$LOCO_LLM_HOME/.git" ]; then
  actual_url="$(git -C "$LOCO_LLM_HOME" remote get-url origin 2>/dev/null || true)"
  case "$actual_url" in
    *"$REMOTE_HOST"*) ;;
    *) die "$LOCO_LLM_HOME exists but origin does not look like ${REMOTE_HOST}." ;;
  esac
  echo "==> updating existing checkout at $LOCO_LLM_HOME"
  git -C "$LOCO_LLM_HOME" fetch --tags --prune origin
elif [ -e "$LOCO_LLM_HOME" ]; then
  die "$LOCO_LLM_HOME already exists and is not a git checkout; refusing to clobber."
else
  echo "==> cloning to $LOCO_LLM_HOME"
  git clone "$REPO_URL" "$LOCO_LLM_HOME"
  git -C "$LOCO_LLM_HOME" fetch --tags --prune origin
fi

cd "$LOCO_LLM_HOME"

if [ -n "$REF_BRANCH" ]; then
  target="$REF_BRANCH"
  echo "==> checking out branch $target"
elif [ -n "$REF_TAG" ]; then
  target="$REF_TAG"
  echo "==> checking out tag $target"
else
  target="$(git tag --list 'v*' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -n 1 || true)"
  [ -n "$target" ] || die "no semver tags found on origin; pass --branch or --tag"
  echo "==> checking out latest tag $target"
fi

git checkout "$target"
if [ -n "$REF_BRANCH" ]; then
  git pull --ff-only origin "$target"
fi

echo "==> creating venv at $LOCO_LLM_HOME/.venv"
uv venv "$LOCO_LLM_HOME/.venv" --python "$PYTHON_MIN"

echo "==> installing loco-llm (editable)"
uv pip install --python "$LOCO_LLM_HOME/.venv/bin/python" -e "$LOCO_LLM_HOME"

bin_dir="$HOME/.local/bin"
mkdir -p "$bin_dir"
ln -sf "$LOCO_LLM_HOME/.venv/bin/llm" "$bin_dir/llm"

case ":$PATH:" in
  *":$bin_dir:"*) ;;
  *) echo "==> add this to your shell profile: export PATH=\"$bin_dir:\$PATH\"" ;;
esac

echo
echo "loco-llm installed to $LOCO_LLM_HOME (ref: $target)"
echo "next: run 'llm setup' to configure"
