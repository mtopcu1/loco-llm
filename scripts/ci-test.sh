#!/usr/bin/env bash
# Mirror .github/workflows/ci.yml "test" job locally (Linux/WSL).
set -euo pipefail

export PATH="${HOME}/.local/bin:/usr/local/bin:${PATH}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -gt 0 ]]; then
  PYTHON_VERSIONS=("$@")
else
  PYTHON_VERSIONS=(3.11 3.12)
fi
FAILED=0

for ver in "${PYTHON_VERSIONS[@]}"; do
  py="python${ver}"
  if ! command -v "$py" >/dev/null 2>&1; then
    echo "error: $py not found (install e.g. sudo apt install python${ver}-venv)" >&2
    FAILED=1
    continue
  fi

  venv=".venv-ci-${ver}"
  echo "=== CI test (Python ${ver}) ==="
  "$py" -m venv "$venv"
  # shellcheck source=/dev/null
  source "$venv/bin/activate"
  python -m pip install --upgrade pip -q
  pip install -e '.[dev]' -q
  echo "--- pytest -q (same as Actions) ---"
  if ! pytest -q; then
    FAILED=1
  fi
  deactivate
  echo ""
done

if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi
echo "All matrix versions passed."
