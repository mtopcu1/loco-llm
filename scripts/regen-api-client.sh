#!/usr/bin/env bash
# Regenerate dashboard/src/api/generated.ts from FastAPI's exported OpenAPI schema.
#
#   scripts/regen-api-client.sh          # write/update generated.ts
#   scripts/regen-api-client.sh --check  # exit non-zero if the file would change
set -euo pipefail

cd "$(dirname "$0")/.."

OUT=dashboard/src/api/generated.ts
TMP_SCHEMA=$(mktemp)
TMP_OUT=$(mktemp)
trap 'rm -f "$TMP_SCHEMA" "$TMP_OUT"' EXIT

python -m llm_cli.webapi.export_openapi > "$TMP_SCHEMA"

if ! command -v npx >/dev/null 2>&1; then
  echo "regen-api-client: npx not found; install Node.js 20+." >&2
  exit 2
fi

(cd dashboard && npx --yes openapi-typescript@7 "../$TMP_SCHEMA" -o "../$TMP_OUT")

if [[ "${1:-}" == "--check" ]]; then
  if ! diff -u "$OUT" "$TMP_OUT" >/dev/null 2>&1; then
    echo "API client out of date. Run: scripts/regen-api-client.sh" >&2
    diff -u "$OUT" "$TMP_OUT" || true
    exit 1
  fi
  echo "API client is up to date."
  exit 0
fi

mkdir -p "$(dirname "$OUT")"
mv "$TMP_OUT" "$OUT"
echo "Wrote $OUT"
