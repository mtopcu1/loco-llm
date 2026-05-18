#!/usr/bin/env bash
# Exit 0 when /v1/models responds with HTTP 200.
set -euo pipefail
python3 - <<'PY'
import os
import urllib.error
import urllib.request

host = os.environ.get("LLM_SERVE_HOST", "127.0.0.1")
port = os.environ["LLM_SERVE_PORT"]
url = f"http://{host}:{port}/v1/models"
try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        code = int(resp.status)
except urllib.error.URLError as exc:
    raise SystemExit(f"healthcheck failed: {exc}") from exc

if code < 200 or code >= 300:
    raise SystemExit(f"healthcheck failed: unexpected status {code}")
PY
