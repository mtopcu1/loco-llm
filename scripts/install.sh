#!/usr/bin/env bash
# Public one-line installer for LocalLLM (pipx + managed scaffold).
# Usage: curl -fsSL https://raw.githubusercontent.com/mtopcu1/local-llm-scaffold/main/scripts/install.sh | bash
set -euo pipefail

# Bump at each release so the script and PyPI wheel stay in lockstep.
# TODO: switch to 0.3.0 when v0.3.0 is tagged and published on PyPI.
PINNED_VERSION="0.2.0"

die() {
  echo "error: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

check_python() {
  need_cmd python3
  python3 - <<'PY' || die "python3 >= 3.11 required"
import sys
if sys.version_info < (3, 11):
    raise SystemExit(1)
PY
}

ensure_pipx() {
  if command -v pipx >/dev/null 2>&1; then
    return 0
  fi
  echo "==> Bootstrapping pipx"
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
}

main() {
  check_python
  need_cmd curl
  need_cmd tar

  ensure_pipx
  export PATH="${HOME}/.local/bin:${PATH}"

  echo "==> Installing localllm-cli==${PINNED_VERSION} via pipx"
  pipx install "localllm-cli==${PINNED_VERSION}" --force

  echo "==> Bootstrapping scaffold assets"
  llm update --scaffold-only --yes

  config_path="${XDG_CONFIG_HOME:-$HOME/.config}/llm/config.yaml"
  if [ ! -f "$config_path" ]; then
    echo
    echo "==> Running first-time setup"
    llm setup
  fi

  echo
  echo "Installed. Make sure ~/.local/bin is on your PATH:"
  echo '  export PATH="$HOME/.local/bin:$PATH"'
  echo
  echo "Next steps:"
  echo "  llm settings show"
  echo "  llm doctor"
  echo "  llm list"
}

main "$@"
