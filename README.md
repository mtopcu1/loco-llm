# LocalLLM

Personal control plane for local LLM runtimes — manage runtime configurations,
benchmark them, and **serve** a chosen config via `llm serve` (foreground, background, or systemd).

This repo contains **text only** — manifests, configs, scripts, benchmark
results. Runtime source trees and model weights live in WSL2's native
filesystem under `~/llm/` (configurable via `llm setup` / `llm settings ...`).

## Getting started (first time)

Inside WSL2 (or any Linux/macOS shell with `git` and Python 3.11+):

```bash
curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"   # if not already
llm setup
```

The installer clones the repo to `~/.loco-llm`, checks out the latest stable
tag, creates a uv venv, and symlinks `llm`. Run `llm doctor` to verify.
See [`docs/INSTALLATION.md`](docs/INSTALLATION.md) for options (`--dir`, `--tag`, `--branch`).

### Updating

```bash
llm update              # latest stable tag
llm update --check      # report current vs. available, no changes
llm update --branch X   # switch to a branch (hotfix testing)
llm update --tag vX.Y.Z # pin to a specific tag (rollback)
```

Bare `llm update` always re-anchors to the latest tag, even if you were on a
branch. See [`docs/UPDATE.md`](docs/UPDATE.md).

### Upgrading from a prior pipx-based install

If you previously installed with `pipx install loco-llm-cli`, switch over:

```bash
pipx uninstall loco-llm-cli || true
rm -f ~/.local/bin/llm
curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
```

### Developer install (git clone)

```bash
git clone https://github.com/mtopcu1/loco-llm.git
cd loco-llm
uv venv && uv pip install -e ".[dev]"
export PATH="$HOME/.local/bin:$PATH"   # optional: uv run llm ...
```

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

For an existing setup, the granular commands still work as before:

```bash
llm runtime setup       # interactive picker (preset or custom)
llm runtime install llamacpp --yes      # non-interactive preset install
llm model pull https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
llm config setup        # interactive
llm config new --runtime llamacpp --model qwen2-7b --param gguf_path='${model_path}'
llm serve llamacpp__qwen2-7b__default
```

For a minimal smoke without llamacpp weights, use `llm runtime install stub-runtime --yes` and `llm serve stub-runtime__default` instead.

See [`docs/lifecycle.md`](docs/lifecycle.md) for modes, switching, and logs. See [`docs/runtime-lifecycle.md`](docs/runtime-lifecycle.md) for `llm runtime install` / `.installed`. User-facing wizard overview: [`docs/wizards.md`](docs/wizards.md).

## Layout

| Path | What it holds |
|---|---|
| `runtimes/{id}/` | Manifest + **`params.yaml`** + build/serve/healthcheck scripts for one runtime |
| `configs/{id}.yaml` | One launch unit (runtime + optional model + flags) |
| `benchmarks/{id}/` | Wrapper around an existing benchmark tool, plus committed results |
| `state/` | Runtime state: `running.json`, `history.jsonl`, `logs/` (gitignored; see `docs/lifecycle.md`) |
| `docs/` | HOWTOs and reference notes |
| `src/llm_cli/` | The Python CLI implementation |

Models are not in the repo — they live per-machine in `$LLM_MODELS/registry.json` plus `$LLM_MODELS/<id>/`. See [`docs/add-a-model.md`](docs/add-a-model.md).

See [`docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md`](docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md)
for the full design.

## CLI commands (Milestone 1–2 + lifecycle)

| Command | Purpose |
|---|---|
| `llm setup` | Interactive first-time configurator. Writes `~/.config/llm/config.yaml`, creates data-root subdirectories, then optional Y/n chain (runtime / model / config / serve). |
| `llm setup --default` | Non-interactive settings only; prints suggested next steps (no chain). |
| `llm advisor` | VRAM-aware param hints (interactive, `--runtime`+`--model`, or `<config-id>`; `--json`). |
| `llm runtime setup` | Wizard: preset official install or author a `kind: custom` runtime in-repo. |
| `llm config new` | Non-interactive config YAML (`--runtime`, optional `--model`, `--param k=v`, `--force`). |
| `llm config setup` | Interactive config YAML with recommendations + review. |
| `llm settings show` | Print settings file path, stored contents, and resolved view. |
| `llm settings env` | Print `export LLM_*=...` lines for `eval "$(llm settings env)"`. |
| `llm settings edit <key>` | Interactive prompt to update one key. |
| `llm settings edit <key> --default` | Reset key to its built-in default (`data_root`) or remove the override (`runtimes_dir`/`models_dir`/`cache_dir`). |
| `llm specs` | Regenerate the auto block in `specs.md` |
| `llm specs --check` | Exit nonzero if `specs.md` differs from current detection |
| `llm specs --print` | Print detection without writing |
| `llm update` | Pull latest stable tag into `LOCO_LLM_HOME` (`--branch`, `--tag`, `--check`, `--restart`) |
| `llm doctor` | Run all checks from `requirements.yaml`; prints a **systemd-linger** advisory when `loginctl` reports `Linger=no` |
| `llm doctor render-requirements` | Regenerate `requirements.md` from `requirements.yaml` |
| `llm list` | List runtimes, models, configs, and benchmarks |
| `llm config show <id>` | Print a single launch config (with `${data_root}` expanded in `serve.params` paths) |
| `llm config validate` | Validate every `configs/*.yaml` against manifests and script layout |
| `llm runtime list` | List discovered runtimes |
| `llm runtime info <id>` | Show manifest path, install record, drift hints |
| `llm runtime install <id>` | Build/install runtime; writes `$LLM_RUNTIMES/<id>/.installed` |
| `llm runtime uninstall <id>` | Remove install marker (optional `--purge` deletes artifacts) |
| `llm runtime rebuild <id>` | Re-run install; `--reset` drops stored build params |
| `llm model list` | List models in `$LLM_MODELS/registry.json` |
| `llm model info <id>` | Show the full registry entry |
| `llm model pull <url-or-id>` | Pull from HF (URL) or refresh an existing id (`--format`, `--include`, `--exclude`, `--id`, `--force`) |
| `llm model add <id> <path> --format <fmt>` | Register local weights via symlink (or copy fallback) |
| `llm model uninstall <id> [--purge]` | Remove a registry entry (and optionally its files) |
| `llm serve <config>` | Start a config (background by default; `--foreground`, `--systemd`) |
| `llm switch <config>` | Stop current + start new config in the same mode |
| `llm stop` | Stop the running service |
| `llm status [--json]` | Show mode, config, port, uptime |
| `llm logs [-f] [-n N]` | Tail logs (file or journalctl) |

Future milestones add `llm bench` / `llm results`.

## Discipline

When you change a workflow:

- Update the corresponding `docs/add-a-*.md` HOWTO **in the same commit** (or immediately after).
- If you add a new external dependency, update `requirements.yaml` and regenerate `requirements.md` in the same commit.
- A HOWTO that's more than two weeks stale relative to actual practice is a bug.

See the [documentation index](docs/README.md).
