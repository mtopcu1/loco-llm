#!/usr/bin/env bash
set -euo pipefail
mkdir -p results
echo '{"ok":true,"bench":"stub-bench"}' > results/stub.json
echo "stub-bench: wrote results/stub.json"
