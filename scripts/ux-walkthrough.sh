#!/usr/bin/env bash
# Manual UX walkthrough helper — logs each step of loco setup to a file.
set -euo pipefail

TEST_HOME="${TEST_HOME:-/tmp/llm-ux-walkthrough-$$}"
LOG_DIR="${TEST_HOME}/ux-logs"
mkdir -p "$LOG_DIR"

export HOME="$TEST_HOME"
export XDG_CONFIG_HOME="$TEST_HOME/.config"
export LOCO_LLM_HOME="/mnt/c/Private/Projects/local-llm-scaffold"
export PYTHONPATH="/mnt/c/Private/Projects/local-llm-scaffold/src"
export TERM="${TERM:-xterm-256color}"

cd "$LOCO_LLM_HOME"

log() {
  echo "=== $* ===" | tee -a "$LOG_DIR/session.log"
}

# Fresh start
rm -rf "$TEST_HOME/.config" "$TEST_HOME/llm" 2>/dev/null || true

log "STEP 1: loco setup — settings prompts (accept defaults)"
# data_root: Enter (default ~/llm)
# layout: Y
# repo_root dev: Y
printf '\n\ny\ny\n' | script -q -c "loco setup" "$LOG_DIR/step1-setup-settings.typescript" 2>&1 \
  | tee "$LOG_DIR/step1-setup-settings.txt" || true

log "STEP 2: runtime setup — pick stub-runtime via plain/TTY"
# Preset branch, stub-runtime (option 2)
printf '1\n2\n' | script -q -c "loco runtime setup" "$LOG_DIR/step2-runtime-setup.typescript" 2>&1 \
  | tee "$LOG_DIR/step2-runtime-setup.txt" || true

log "STEP 3: config setup — stub-runtime smoke config"
printf 'N\nS\n' | script -q -c "loco config setup --runtime stub-runtime" "$LOG_DIR/step3-config-setup.typescript" 2>&1 \
  | tee "$LOG_DIR/step3-config-setup.txt" || true

log "STEP 4: loco status (after no serve yet)"
loco status 2>&1 | tee "$LOG_DIR/step4-status.txt" || true

log "STEP 5: loco serve stub-runtime__default (foreground, 3s timeout)"
timeout 3 loco serve stub-runtime__default 2>&1 | tee "$LOG_DIR/step5-serve-fg.txt" || true

log "STEP 6: loco serve background"
loco serve stub-runtime__default --background 2>&1 | tee "$LOG_DIR/step6-serve-bg.txt" || true
sleep 1
loco status 2>&1 | tee "$LOG_DIR/step6-status.txt" || true
loco stop 2>&1 | tee "$LOG_DIR/step6-stop.txt" || true

log "ARTIFACTS"
echo "TEST_HOME=$TEST_HOME"
echo "LOG_DIR=$LOG_DIR"
find "$TEST_HOME" -name '*.yaml' -o -name '.installed' 2>/dev/null | sort
cat "$TEST_HOME/.config/llm/config.yaml" 2>/dev/null || true
