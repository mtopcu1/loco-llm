#!/usr/bin/env bash
# Contributor install from a git clone (editable pipx + llm-dev).
# Run from the repository root: ./scripts/install-dev.sh
#
# Installs `llm-dev` via pipx --editable so src/ changes apply immediately.
# Sets repo_root to this checkout so scaffold assets are read from the clone.
# Stable `llm` (pipx public install) and `llm-dev` can coexist on one machine.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

die() {
  echo "error: $*" >&2
  exit 1
}

check_python() {
  command -v python3 >/dev/null 2>&1 || die "python3 not found"
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

set_repo_root_in_settings() {
  local llm_dev
  llm_dev="$(command -v llm-dev)"
  local venv_python
  venv_python="$(dirname "$(readlink -f "$llm_dev" 2>/dev/null || echo "$llm_dev")")/python"
  "$venv_python" - "$REPO_ROOT" <<'PY'
import sys
from pathlib import Path

from llm_cli.core.settings import load_settings, save_settings

repo_root = Path(sys.argv[1]).resolve()
stored = load_settings()
stored["repo_root"] = str(repo_root)
path = save_settings(stored)
print(path)
PY
}

main() {
  check_python
  ensure_pipx
  export PATH="${HOME}/.local/bin:${PATH}"

  echo "==> Installing editable loco-llm-cli as llm-dev"
  pipx install --editable . --force --suffix=-dev

  config_path="${XDG_CONFIG_HOME:-$HOME/.config}/llm/config.yaml"
  if [ ! -f "$config_path" ]; then
    echo "==> Running llm-dev setup --default"
    llm-dev setup --default
  else
    echo "==> Setting repo_root to ${REPO_ROOT} (existing settings preserved)"
    set_repo_root_in_settings
  fi

  echo
  echo "Dev install ready. Make sure ~/.local/bin is on your PATH:"
  echo '  export PATH="$HOME/.local/bin:$PATH"'
  echo
  echo "Use llm-dev for branch/PR testing; keep llm for the stable pipx install."
}

main "$@"
