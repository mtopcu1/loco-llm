#!/usr/bin/env bash
# API-driven rerun of full-runtime-serve workflow (subset when assets exist).
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:7878/api}"
HDR=(-H "Content-Type: application/json")

log() { echo "[$(date +%H:%M:%S)] $*"; }

json_get() { curl -sf "${HDR[@]}" "$BASE$1"; }
json_post() { curl -sf "${HDR[@]}" -X POST -d "$2" "$BASE$1"; }

log "=== health ==="
json_get /health | head -c 80; echo

log "=== SPA deep link /models (non-API) ==="
code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:7878/models")
echo "GET /models -> $code"

log "=== runtimes ==="
json_get /runtimes | python3 -c "import sys,json; d=json.load(sys.stdin); print([(r['id'],r.get('installed')) for r in d])"

log "=== F8: dual start (expect 409) ==="
CFG="${CFG:-llamacpp__qwen-0.5b__default}"
# ensure something running
json_post /instance/stop '{}' >/dev/null 2>&1 || true
sleep 1
jid=$(json_post /instance/start "{\"config_id\":\"$CFG\",\"mode\":\"background\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
log "start job $jid"
for i in $(seq 1 60); do
  st=$(json_get "/jobs/$jid" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  [[ "$st" == "running" || "$st" == "queued" ]] && sleep 1 && continue
  break
done
st=$(json_get "/jobs/$jid" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
log "first start status=$st"
code=$(curl -s -o /tmp/dual.json -w "%{http_code}" "${HDR[@]}" -X POST -d "{\"config_id\":\"vllm__qwen-0.5b__default\",\"mode\":\"background\"}" "$BASE/instance/start")
log "second start HTTP $code body=$(cat /tmp/dual.json)"

log "=== F1: repo_root token (python) ==="
/home/melih/.loco/install/.venv/bin/python - <<'PY'
from pathlib import Path
import os
from llm_cli.core.params import expand_path
from llm_cli.core.settings import Settings
install = Path(os.environ.get("LOCO_INSTALL", Path.home() / ".loco" / "install"))
s = Settings(
    data_root=Path.home() / ".loco",
    repo_root=None,
    runtimes_dir=Path.home() / ".loco" / "runtimes",
    models_dir=Path.home() / ".loco" / "models",
    cache_dir=Path.home() / ".loco" / "cache",
)
print("expand:", expand_path("${repo_root}/runtimes", s))
PY

log "=== instance / switch timing ==="
ALT="${ALT:-llamacpp__qwen-0.5b__alt}"
t0=$(date +%s)
sj=$(json_post /instance/switch "{\"config_id\":\"$ALT\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
for i in $(seq 1 120); do
  st=$(json_get "/jobs/$sj" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  [[ "$st" == "running" || "$st" == "queued" ]] && sleep 1 && continue
  break
done
dt=$(($(date +%s)-t0))
st=$(json_get "/jobs/$sj" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
log "switch status=$st elapsed=${dt}s"

json_post /instance/stop '{}' >/dev/null || true
sleep 2

log "=== orphan check (llama-server / hf download) ==="
ps aux | grep -E 'llama-server|hf download|vllm' | grep -v grep || echo "(none)"

log "=== done ==="
