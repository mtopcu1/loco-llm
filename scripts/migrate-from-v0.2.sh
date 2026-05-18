#!/usr/bin/env bash
# Migrate a v0.2.x editable-clone install to the v0.3.0 distributed layout.
# Idempotent; dry-run by default. Run inside your existing git clone (WSL/Linux).
set -euo pipefail

# Bump when cutting the migration release.
TARGET_CLI_VERSION="0.3.0"
MIGRATE_TAG="${LOCALLLM_MIGRATE_TAG:-v0.3.0}"

APPLY=0
ON_CONFLICT=""

usage() {
  cat <<'EOF'
Usage: ./scripts/migrate-from-v0.2.sh [OPTIONS]

Migrate from v0.2.x (editable venv + repo_root) to v0.3.0 (pipx + managed scaffold).

Options:
  --plan              Print migration plan only (default)
  --apply             Execute the migration plan
  --on-conflict=MODE  Non-interactive conflict handling: keep | discard | abort
  -h, --help          Show this help

Examples:
  ./scripts/migrate-from-v0.2.sh
  ./scripts/migrate-from-v0.2.sh --apply --on-conflict=keep
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

PYTHON="${PYTHON:-python3}"

# Prefer the v0.2 editable venv (has PyYAML) when migrating from a typical install.
detect_python() {
  local config_path="${XDG_CONFIG_HOME:-$HOME/.config}/llm/config.yaml"
  local data_root="${LLM_DATA_ROOT:-$HOME/llm}"
  if [ -f "$config_path" ]; then
    local line
    line="$(grep -E '^data_root:' "$config_path" | head -1 || true)"
    if [ -n "$line" ]; then
      data_root="${line#data_root:}"
      data_root="${data_root#"${data_root%%[![:space:]]*}"}"
      data_root="${data_root%"${data_root##*[![:space:]]}"}"
      data_root="${data_root/#\~/$HOME}"
    fi
  fi
  local venv_py="${data_root}/.cli-venv/bin/python"
  if [ -x "$venv_py" ]; then
    PYTHON="$venv_py"
  fi
}

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --plan)
        APPLY=0
        ;;
      --apply)
        APPLY=1
        ;;
      --on-conflict=*)
        ON_CONFLICT="${1#--on-conflict=}"
        case "$ON_CONFLICT" in
          keep | discard | abort) ;;
          *) die "invalid --on-conflict=$ON_CONFLICT (use keep, discard, or abort)" ;;
        esac
        ;;
      -h | --help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
    shift
  done
}

ensure_pipx() {
  if command -v pipx >/dev/null 2>&1; then
    return 0
  fi
  echo "==> Bootstrapping pipx"
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
  export PATH="${HOME}/.local/bin:${PATH}"
}

# Emit shell-assignable variables: REPO_ROOT DATA_ROOT CONFIG_PATH SCAFFOLD_DIR USER_DIR
load_paths() {
  eval "$("$PYTHON" - <<'PY'
import os
from pathlib import Path

import yaml

xdg_cfg = os.environ.get("XDG_CONFIG_HOME")
cfg_base = Path(xdg_cfg).expanduser() if xdg_cfg else Path.home() / ".config"
config_path = cfg_base / "llm" / "config.yaml"

stored = {}
if config_path.is_file():
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        stored = {str(k): str(v) for k, v in raw.items()}

repo_raw = stored.get("repo_root") or os.environ.get("LLM_REPO_ROOT")
if not repo_raw:
    raise SystemExit("repo_root not set in config and LLM_REPO_ROOT unset")
repo_root = Path(repo_raw).expanduser().resolve()
if not repo_root.is_dir():
    raise SystemExit(f"repo_root is not a directory: {repo_root}")

data_raw = stored.get("data_root") or os.environ.get("LLM_DATA_ROOT") or "~/llm"
data_root = Path(data_raw).expanduser().resolve()

xdg_data = os.environ.get("XDG_DATA_HOME")
scaffold = (
    Path(os.environ["LLM_SCAFFOLD_DIR"]).expanduser()
    if os.environ.get("LLM_SCAFFOLD_DIR")
    else (Path(xdg_data).expanduser() if xdg_data else Path.home() / ".local" / "share")
    / "localllm"
    / "scaffold"
)
user_dir = data_root / "user"

def q(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"

print(f"REPO_ROOT={q(str(repo_root))}")
print(f"DATA_ROOT={q(str(data_root))}")
print(f"CONFIG_PATH={q(str(config_path))}")
print(f"SCAFFOLD_DIR={q(str(scaffold))}")
print(f"USER_DIR={q(str(user_dir))}")
PY
)"
}

verify_tag() {
  if ! git -C "$REPO_ROOT" rev-parse "${MIGRATE_TAG}^{commit}" >/dev/null 2>&1; then
    die "git tag ${MIGRATE_TAG} not found. Run: git fetch --tags"
  fi
}

# Write analysis files under a temp dir; source shell snippets from them.
run_analysis() {
  ANALYSIS_DIR="$(mktemp -d)"
  trap 'rm -rf "$ANALYSIS_DIR"' RETURN
  export ANALYSIS_DIR REPO_ROOT MIGRATE_TAG USER_DIR
  "$PYTHON" - <<'PY'
import os
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(os.environ["REPO_ROOT"])
tag = os.environ["MIGRATE_TAG"]
user_dir = Path(os.environ["USER_DIR"])
out = Path(os.environ["ANALYSIS_DIR"])

def git_paths(prefix: str) -> set[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", tag, "--", prefix],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or f"git ls-tree failed for {tag}:{prefix}")
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}

def read_git_file(path: str) -> bytes | None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", f"{tag}:{path}"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout

tag_runtime_dirs = {
    p.split("/")[1]
    for p in git_paths("runtimes")
    if p.startswith("runtimes/") and "/" in p[len("runtimes/") :]
}
tag_config_files = {
    Path(p).name
    for p in git_paths("configs")
    if p.startswith("configs/") and p.endswith((".yaml", ".yml"))
}

user_moves: list[tuple[str, str]] = []
conflicts: list[tuple[str, str, str]] = []

runtimes_root = repo / "runtimes"
if runtimes_root.is_dir():
    for child in sorted(runtimes_root.iterdir()):
        if not child.is_dir():
            continue
        rt_id = child.name
        if rt_id not in tag_runtime_dirs:
            dest = user_dir / "runtimes" / rt_id
            user_moves.append((str(child), str(dest)))
            continue
        for path in sorted(child.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(repo).as_posix()
            tag_bytes = read_git_file(rel)
            if tag_bytes is None:
                continue
            local = path.read_bytes()
            if local != tag_bytes:
                dest = user_dir / "runtimes" / f"{rt_id}-local" / path.relative_to(child)
                conflicts.append((rel, str(path), str(dest)))

configs_root = repo / "configs"
if configs_root.is_dir():
    for path in sorted(configs_root.glob("*.yaml")):
        rel = path.relative_to(repo).as_posix()
        name = path.name
        if name not in tag_config_files:
            dest = user_dir / "configs" / name
            user_moves.append((str(path), str(dest)))
            continue
        tag_bytes = read_git_file(rel)
        if tag_bytes is not None and path.read_bytes() != tag_bytes:
            dest = user_dir / "configs" / name
            conflicts.append((rel, str(path), str(dest)))

(out / "user_moves.txt").write_text(
    "\n".join(f"{src}\t{dst}" for src, dst in user_moves),
    encoding="utf-8",
)
(out / "conflicts.txt").write_text(
    "\n".join(f"{rel}\t{src}\t{dst}" for rel, src, dst in conflicts),
    encoding="utf-8",
)
PY
}

print_plan() {
  local venv_dir="${DATA_ROOT}/.cli-venv"
  local llm_link="${HOME}/.local/bin/llm"
  echo "Migration plan for ${REPO_ROOT} → ${TARGET_CLI_VERSION}"
  echo
  echo "Detected current layout:"
  echo "  repo_root        : ${REPO_ROOT}    (v0.2.0 editable install)"
  echo "  data_root        : ${DATA_ROOT}"
  echo "  LLM_SCAFFOLD_DIR : ${SCAFFOLD_DIR}  (will be created)"
  echo "  LLM_USER_DIR     : ${USER_DIR}      (will be created)"
  echo

  if [ -s "${ANALYSIS_DIR}/user_moves.txt" ]; then
    echo "User-authored items to be moved out of repo_root:"
    while IFS=$'\t' read -r src dst; do
      [ -z "$src" ] && continue
      echo "  ${src}  ->  ${dst}"
    done <"${ANALYSIS_DIR}/user_moves.txt"
    echo
  else
    echo "User-authored items to be moved out of repo_root: (none)"
    echo
  fi

  if [ -s "${ANALYSIS_DIR}/conflicts.txt" ]; then
    echo "Shipped items with local modifications (need your call):"
    while IFS=$'\t' read -r rel src dst; do
      [ -z "$rel" ] && continue
      echo "  ${rel}  (modified vs ${MIGRATE_TAG})"
      echo "    [k]eep modified copy as ${dst}"
      echo "    [d]iscard modifications"
      echo "    [a]bort migration"
    done <"${ANALYSIS_DIR}/conflicts.txt"
    echo
  fi

  echo "CLI install changes:"
  if [ -L "$llm_link" ] || [ -f "$llm_link" ]; then
    echo "  remove   ${llm_link} symlink"
  fi
  if [ -d "$venv_dir" ]; then
    echo "  remove   ${venv_dir}  (after confirming pipx install works)"
  fi
  echo "  install  pipx install localllm-cli==${TARGET_CLI_VERSION}"
  echo
  echo "Settings changes:"
  echo "  unset    repo_root  (was: ${REPO_ROOT})"
  echo "           (kept in ${CONFIG_PATH}.bak)"
  echo
  if [ "$APPLY" -eq 0 ]; then
    echo "Run with --apply to execute this plan."
  fi
}

resolve_conflict() {
  local rel="$1" src="$2" dst="$3"
  local choice="$ON_CONFLICT"
  if [ -z "$choice" ]; then
    echo
    echo "Conflict: ${rel}"
    while true; do
      read -r -p "  [k]eep / [d]iscard / [a]bort? " choice
      choice="$(echo "$choice" | tr '[:upper:]' '[:lower:]')"
      case "$choice" in
        k | keep) choice=keep ;;
        d | discard) choice=discard ;;
        a | abort) choice=abort ;;
        *) echo "  Enter k, d, or a." ;;
      esac
      [ -n "$choice" ] && break
    done
  fi
  case "$choice" in
    keep)
      mkdir -p "$(dirname "$dst")"
      cp -a "$src" "$dst"
      echo "  kept: ${dst}"
      ;;
    discard)
      echo "  discarded: ${rel}"
      ;;
    abort)
      die "migration aborted at ${rel}"
      ;;
    *)
      die "internal: bad conflict choice"
      ;;
  esac
}

copy_user_moves() {
  if [ ! -s "${ANALYSIS_DIR}/user_moves.txt" ]; then
    return 0
  fi
  while IFS=$'\t' read -r src dst; do
    [ -z "$src" ] && continue
    mkdir -p "$(dirname "$dst")"
    if [ -d "$src" ]; then
      rm -rf "$dst"
      cp -a "$src" "$dst"
    else
      cp -a "$src" "$dst"
    fi
    echo "  copied: ${src} -> ${dst}"
  done <"${ANALYSIS_DIR}/user_moves.txt"
}

apply_conflicts() {
  if [ ! -s "${ANALYSIS_DIR}/conflicts.txt" ]; then
    return 0
  fi
  while IFS=$'\t' read -r rel src dst; do
    [ -z "$rel" ] && continue
    resolve_conflict "$rel" "$src" "$dst"
  done <"${ANALYSIS_DIR}/conflicts.txt"
}

backup_config() {
  cp -a "$CONFIG_PATH" "${CONFIG_PATH}.bak"
  echo "  backed up: ${CONFIG_PATH} -> ${CONFIG_PATH}.bak"
}

unset_repo_root() {
  local py="${PYTHON}"
  if command -v llm >/dev/null 2>&1; then
    py="$(dirname "$(readlink -f "$(command -v llm)" 2>/dev/null || command -v llm)")/python"
  fi
  "$py" - "$CONFIG_PATH" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
raw = yaml.safe_load(path.read_text(encoding="utf-8"))
if not isinstance(raw, dict):
    raw = {}
stored = {str(k): str(v) for k, v in raw.items()}
stored.pop("repo_root", None)
order = ("data_root", "repo_root", "runtimes_dir", "models_dir", "cache_dir")
ordered = {k: stored[k] for k in order if k in stored}
path.write_text(
    yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True),
    encoding="utf-8",
)
PY
  echo "  unset repo_root in ${CONFIG_PATH}"
}

restore_on_failure() {
  local venv_llm="${DATA_ROOT}/.cli-venv/bin/llm"
  local llm_link="${HOME}/.local/bin/llm"
  if [ -f "${CONFIG_PATH}.bak" ]; then
    cp -a "${CONFIG_PATH}.bak" "$CONFIG_PATH"
    echo "  restored ${CONFIG_PATH} from backup"
  fi
  if [ -x "$venv_llm" ]; then
    mkdir -p "${HOME}/.local/bin"
    ln -sf "$venv_llm" "$llm_link"
    echo "  restored ${llm_link} -> ${venv_llm}"
  fi
}

apply_migration() {
  local venv_dir="${DATA_ROOT}/.cli-venv"
  local venv_llm="${venv_dir}/bin/llm"
  local llm_link="${HOME}/.local/bin/llm"
  local old_llm_target=""

  echo "==> Applying migration"
  backup_config

  echo "==> Copying user content to ${USER_DIR}"
  mkdir -p "${USER_DIR}/runtimes" "${USER_DIR}/configs" "${USER_DIR}/benchmarks"
  copy_user_moves
  apply_conflicts

  ensure_pipx
  export PATH="${HOME}/.local/bin:${PATH}"

  if [ -L "$llm_link" ] || [ -e "$llm_link" ]; then
    old_llm_target="$(readlink -f "$llm_link" 2>/dev/null || true)"
    rm -f "$llm_link"
    echo "  removed: ${llm_link}"
  fi

  echo "==> Installing localllm-cli==${TARGET_CLI_VERSION} via pipx"
  if ! pipx install "localllm-cli==${TARGET_CLI_VERSION}" --force; then
    restore_on_failure
    die "pipx install failed; config and llm symlink restored where possible"
  fi

  echo "==> Initializing scaffold"
  if ! llm update --scaffold-only --yes; then
    restore_on_failure
    die "llm update --scaffold-only failed; config and llm symlink restored where possible"
  fi

  echo "==> Smoke test"
  if ! llm --version >/dev/null 2>&1; then
    restore_on_failure
    die "llm --version failed"
  fi
  if ! llm list >/dev/null 2>&1; then
    restore_on_failure
    die "llm list failed"
  fi
  if ! llm doctor --quick >/dev/null 2>&1; then
    restore_on_failure
    die "llm doctor --quick failed"
  fi
  echo "  smoke test passed"

  unset_repo_root

  echo
  echo "Migration complete."
  echo "  - Config backup: ${CONFIG_PATH}.bak"
  echo "  - Old clone at ${REPO_ROOT} is no longer required for normal use."
  if [ -d "$venv_dir" ]; then
    echo "  - You may remove the old venv when ready: ${venv_dir}"
  fi
  if [ -n "$old_llm_target" ] && [ "$old_llm_target" != "$(command -v llm 2>/dev/null || true)" ]; then
    echo "  - Previous llm pointed at: ${old_llm_target}"
  fi
}

main() {
  parse_args "$@"
  command -v python3 >/dev/null 2>&1 || die "python3 required"
  command -v git >/dev/null 2>&1 || die "git required (v0.2.x migration runs from your clone)"
  detect_python

  load_paths
  verify_tag
  run_analysis
  print_plan

  if [ "$APPLY" -eq 1 ]; then
    apply_migration
  fi
}

main "$@"
