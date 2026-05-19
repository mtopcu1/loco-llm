#!/usr/bin/env bash
# Run CI on a fresh clone under the WSL Linux filesystem (closer to ubuntu-latest).
set -euo pipefail

export PATH="${HOME}/.local/bin:/usr/local/bin:${PATH}"

CLONE_DIR="${HOME}/llm-ci-test"
REPO_URL="${REPO_URL:-https://github.com/mtopcu1/local-llm-scaffold.git}"
BRANCH="${BRANCH:-feat/v0.3-distributed-install}"

if [[ $# -gt 0 ]]; then
  PYTHON_VERSIONS=("$@")
else
  PYTHON_VERSIONS=(3.11 3.12)
fi

rm -rf "$CLONE_DIR"
git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$CLONE_DIR"
cd "$CLONE_DIR"

FAILED=0
for ver in "${PYTHON_VERSIONS[@]}"; do
  py="python${ver}"
  if ! command -v "$py" >/dev/null 2>&1; then
    echo "error: $py not found" >&2
    FAILED=1
    continue
  fi

  echo "=== Fresh clone CI test (Python ${ver}) @ ${CLONE_DIR} ==="
  venv=".venv-ci-${ver}"
  "$py" -m venv "$venv"
  # shellcheck source=/dev/null
  source "$venv/bin/activate"
  python -m pip install --upgrade pip -q
  pip install -e '.[dev]' -q
  pytest -q || FAILED=1
  deactivate
  echo ""
done

exit "$FAILED"
