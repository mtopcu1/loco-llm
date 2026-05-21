#!/usr/bin/env bash
# Move models from legacy ~/llm/models into ~/.loco/models and merge registry.json.
set -euo pipefail

LOCO_MODELS="${LOCO_HOME:-$HOME/.loco}/models"
LEGACY="${LEGACY_MODELS:-$HOME/llm/models}"

if [[ ! -d "$LEGACY" ]]; then
  echo "No legacy models dir at $LEGACY — nothing to migrate."
  exit 0
fi

mkdir -p "$LOCO_MODELS"
python3 - "$LEGACY" "$LOCO_MODELS" <<'PY'
import json
import shutil
import sys
from pathlib import Path

legacy = Path(sys.argv[1])
loco = Path(sys.argv[2])

def load_reg(path: Path) -> dict:
    p = path / "registry.json"
    if not p.is_file():
        return {"version": 1, "models": {}}
    return json.loads(p.read_text(encoding="utf-8"))

reg = load_reg(loco)
old = load_reg(legacy)

for model_id, entry in old.get("models", {}).items():
    src = legacy / model_id
    dst = loco / model_id
    if src.is_dir():
        if dst.exists():
            print(f"skip move (exists): {model_id}")
        else:
            shutil.move(str(src), str(dst))
            print(f"moved: {model_id} -> {dst}")
    reg.setdefault("models", {})[model_id] = entry
    print(f"registered: {model_id}")

(loco / "registry.json").write_text(
    json.dumps(reg, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"Wrote {loco / 'registry.json'}")
PY

echo "Done. Verify with: loco model list"
