#!/usr/bin/env bash
# Simulate GitHub Actions pull_request checkout (refs/pull/N/merge).
set -euo pipefail
export PATH="${HOME}/.local/bin:/usr/local/bin:${PATH}"

PR="${PR:-2}"
CLONE="${CLONE:-${HOME}/llm-ci-pr-merge}"
REPO_URL="${REPO_URL:-https://github.com/mtopcu1/local-llm-scaffold.git}"

rm -rf "$CLONE"
mkdir -p "$CLONE"
git clone "$REPO_URL" "$CLONE"
cd "$CLONE"
git fetch origin "pull/${PR}/merge:pr-merge"
git checkout pr-merge

py="${PYTHON:-python3.12}"
echo "=== PR merge ref (pull/${PR}/merge) on $($py -V) ==="
$py -m venv .venv
# shellcheck source=/dev/null
source .venv/bin/activate
python -m pip install --upgrade pip -q
pip install --no-cache-dir -e ".[dev]" -q
env CI=true NO_COLOR=1 TERM=dumb pytest -q --tb=short
