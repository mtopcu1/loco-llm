#!/usr/bin/env bash
# Public one-line installer for loco-llm.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
# Options:
#   --data-home <path>  user data root (default: $HOME/.loco)
#   --dir <path>        git install root (default: $DATA_HOME/install)
#   --branch <name>     clone+checkout a branch instead of the latest tag
#   --tag <vX.Y.Z>      pin to a specific tag
set -euo pipefail

REPO_URL="https://github.com/mtopcu1/loco-llm.git"
REMOTE_HOST="github.com/mtopcu1/loco-llm"
LOCO_HOME="${LOCO_HOME:-${LOCO_LLM_DATA:-$HOME/.loco}}"
LOCO_INSTALL="${LOCO_INSTALL:-${LOCO_LLM_HOME:-}}"
PYTHON_MIN="3.11"
REF_BRANCH=""
REF_TAG=""
die() { echo "error: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --data-home) LOCO_HOME="$2"; shift 2 ;;
    --dir)       LOCO_INSTALL="$2"; shift 2 ;;
    --branch)    REF_BRANCH="$2"; shift 2 ;;
    --tag)       REF_TAG="$2"; shift 2 ;;
    *)           die "unknown argument: $1" ;;
  esac
done

if [ -z "$LOCO_INSTALL" ]; then
  LOCO_INSTALL="$LOCO_HOME/install"
fi

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

if [ -d "$LOCO_INSTALL/.git" ]; then
  actual_url="$(git -C "$LOCO_INSTALL" remote get-url origin 2>/dev/null || true)"
  case "$actual_url" in
    *"$REMOTE_HOST"*) ;;
    *) die "$LOCO_INSTALL exists but origin does not look like ${REMOTE_HOST}." ;;
  esac
  echo "==> updating existing checkout at $LOCO_INSTALL"
  git -C "$LOCO_INSTALL" fetch --tags --prune origin
elif [ -e "$LOCO_INSTALL" ]; then
  die "$LOCO_INSTALL already exists and is not a git checkout; refusing to clobber."
else
  mkdir -p "$(dirname "$LOCO_INSTALL")"
  echo "==> cloning to $LOCO_INSTALL"
  git clone "$REPO_URL" "$LOCO_INSTALL"
  git -C "$LOCO_INSTALL" fetch --tags --prune origin
fi

cd "$LOCO_INSTALL"

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

echo "==> creating venv at $LOCO_INSTALL/.venv"
uv venv "$LOCO_INSTALL/.venv" --python "$PYTHON_MIN"

echo "==> installing loco-llm (editable)"
uv pip install --python "$LOCO_INSTALL/.venv/bin/python" -e "$LOCO_INSTALL"

bin_dir="$HOME/.local/bin"
mkdir -p "$bin_dir"
ln -sf "$LOCO_INSTALL/.venv/bin/loco" "$bin_dir/loco"
rm -f "$bin_dir/llm" 2>/dev/null || true

case ":$PATH:" in
  *":$bin_dir:"*) ;;
  *) echo "==> add this to your shell profile: export PATH=\"$bin_dir:\$PATH\"" ;;
esac

echo "==> preparing data home at $LOCO_HOME"
mkdir -p "$LOCO_HOME"/{configs,models,runtimes,cache,state,user/runtimes,user/benchmarks,install}

if [ ! -f "$LOCO_HOME/config.yaml" ]; then
  printf 'data_root: %s\n' "$LOCO_HOME" > "$LOCO_HOME/config.yaml"
  echo "==> wrote $LOCO_HOME/config.yaml"
else
  echo "==> keeping existing $LOCO_HOME/config.yaml"
fi

if [ -d "$LOCO_INSTALL/configs" ]; then
  for f in "$LOCO_INSTALL"/configs/*.yaml; do
    [ -f "$f" ] || continue
    base="$(basename "$f")"
    dest="$LOCO_HOME/configs/$base"
    if [ ! -f "$dest" ]; then
      cp "$f" "$dest"
      echo "==> seeded config $base"
    fi
  done
fi

export LOCO_HOME
export LOCO_INSTALL

echo
echo "loco-llm installed"
echo "  data:    $LOCO_HOME"
echo "  code:    $LOCO_INSTALL (ref: $target)"
echo "next: loco setup    # first-run wizard (runtime, model, config)"
echo "      loco doctor   # verify environment"
