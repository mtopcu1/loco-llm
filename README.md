# LocalLLM

Personal control plane for local LLM runtimes — manage runtime configurations,
benchmark them, and **serve** a chosen config via `llm serve` (foreground, background, or systemd).

This repo contains **text only** — manifests, configs, scripts, benchmark
results. Runtime source trees and model weights live in WSL2's native
filesystem under `~/llm/` (configurable via `llm setup` / `llm settings ...`).

## Getting started (first time)

Inside WSL2:

```bash
# Public install (no git clone)
curl -fsSL https://raw.githubusercontent.com/mtopcu1/local-llm-scaffold/main/scripts/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"   # if not already

# Or, if you already use pipx:
pipx install loco-llm-cli
llm setup
```

`llm setup` runs on first use if you skipped it during install. Verify prerequisites with `llm doctor` (or read `requirements.md` before install).

### Upgrading from 0.2.x

If you installed via the old editable clone + `./install.sh`, migrate in place:

```bash
cd ~/local-llm-scaffold   # your existing clone
git fetch && git checkout v0.3.0
./scripts/migrate-from-v0.2.sh
# review the plan, then:
./scripts/migrate-from-v0.2.sh --apply
```

### Developer install (git clone)

```bash
git clone https://github.com/mtopcu1/local-llm-scaffold.git
cd local-llm-scaffold
./scripts/install-dev.sh
export PATH="$HOME/.local/bin:$PATH"
llm-dev setup    # if install-dev.sh did not run setup
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for branch/PR workflow (`llm-dev` vs stable `llm`).

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
