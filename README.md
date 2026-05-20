# LocalLLM

Personal control plane for local LLM runtimes — manage runtime configurations,
benchmark them, and **serve** a chosen config via `loco serve` (foreground, background, or systemd).

This repo contains **text only** — manifests, configs, scripts, benchmark
results. Runtime source trees and model weights live in WSL2's native
filesystem under `~/.loco/` (configurable via `loco setup` / `loco settings ...`).

## Getting started (first time)

Inside WSL2 (or any Linux/macOS shell with `git` and Python 3.11+):

```bash
curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"   # if not already
loco doctor
```

The installer uses a Hermes-style layout: data at `~/.loco`, git checkout at
`~/.loco/install`, seeds example configs, then runs `loco setup --default`.
See [`docs/INSTALLATION.md`](docs/INSTALLATION.md) for options (`--data-home`, `--dir`, `--tag`, `--branch`).

### Updating

```bash
loco update              # latest stable tag
loco update --check      # report current vs. available, no changes
loco update --branch X   # switch to a branch (hotfix testing)
loco update --tag vX.Y.Z # pin to a specific tag (rollback)
```

Bare `loco update` always re-anchors to the latest tag, even if you were on a
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
export PATH="$HOME/.local/bin:$PATH"   # optional: uv run loco ...
```

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

For an existing setup, the granular commands still work as before:

```bash
loco runtime setup       # interactive picker (preset or custom)
loco runtime install llamacpp --yes      # non-interactive preset install
loco model pull https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
loco config setup        # interactive
loco config new --runtime llamacpp --model qwen2-7b --param gguf_path='${model_path}'
loco serve llamacpp__qwen2-7b__default
```

For a minimal smoke without llamacpp weights, use `loco runtime install stub-runtime --yes` and `loco serve stub-runtime__default` instead.

See [`docs/lifecycle.md`](docs/lifecycle.md) for modes, switching, and logs. See [`docs/runtime-lifecycle.md`](docs/runtime-lifecycle.md) for `loco runtime install` / `.installed`. User-facing wizard overview: [`docs/wizards.md`](docs/wizards.md).

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
| `loco setup` | Configure `~/.loco/config.yaml` and data-home layout. |
| `loco setup --default` | Non-interactive; refresh settings and print next steps. |
| `loco advisor` | VRAM-aware param hints (interactive, `--runtime`+`--model`, or `<config-id>`; `--json`). |
| `loco runtime setup` | Wizard: preset official install or author a `kind: custom` runtime in-repo. |
| `loco config new` | Non-interactive config YAML (`--runtime`, optional `--model`, `--param k=v`, `--force`). |
| `loco config setup` | Interactive config YAML with recommendations + review. |
| `loco settings show` | Print settings file path, stored contents, and resolved view. |
| `loco settings env` | Print `export LLM_*=...` lines for `eval "$(llm settings env)"`. |
| `loco settings edit <key>` | Interactive prompt to update one key. |
| `loco settings edit <key> --default` | Reset key to its built-in default (`data_root`) or remove the override (`runtimes_dir`/`models_dir`/`cache_dir`). |
| `loco specs` | Regenerate the auto block in `specs.md` |
| `loco specs --check` | Exit nonzero if `specs.md` differs from current detection |
| `loco specs --print` | Print detection without writing |
| `loco update` | Pull latest stable tag into `LOCO_INSTALL` (`--branch`, `--tag`, `--check`, `--restart`) |
| `loco doctor` | Run all checks from `requirements.yaml`; prints a **systemd-linger** advisory when `loginctl` reports `Linger=no` |
| `loco doctor render-requirements` | Regenerate `requirements.md` from `requirements.yaml` |
| `loco list` | List runtimes, models, configs, and benchmarks |
| `loco config show <id>` | Print a single launch config (with `${data_root}` expanded in `serve.params` paths) |
| `loco config validate` | Validate every `configs/*.yaml` against manifests and script layout |
| `loco runtime list` | List discovered runtimes |
| `loco runtime info <id>` | Show manifest path, install record, drift hints |
| `loco runtime install <id>` | Build/install runtime; writes `$LLM_RUNTIMES/<id>/.installed` |
| `loco runtime uninstall <id>` | Remove install marker (optional `--purge` deletes artifacts) |
| `loco runtime rebuild <id>` | Re-run install; `--reset` drops stored build params |
| `loco model list` | List models in `$LLM_MODELS/registry.json` |
| `loco model info <id>` | Show the full registry entry |
| `loco model pull <url-or-id>` | Pull from HF (URL) or refresh an existing id (`--format`, `--include`, `--exclude`, `--id`, `--force`) |
| `loco model add <id> <path> --format <fmt>` | Register local weights via symlink (or copy fallback) |
| `loco model uninstall <id> [--purge]` | Remove a registry entry (and optionally its files) |
| `loco serve <config>` | Start a config (background by default; `--foreground`, `--systemd`) |
| `loco switch <config>` | Stop current + start new config in the same mode |
| `loco stop` | Stop the running service |
| `loco status [--json]` | Show mode, config, port, uptime |
| `loco logs [-f] [-n N]` | Tail logs (file or journalctl) |

Future milestones add `loco bench` / `loco results`.

## Discipline

When you change a workflow:

- Update the corresponding `docs/add-a-*.md` HOWTO **in the same commit** (or immediately after).
- If you add a new external dependency, update `requirements.yaml` and regenerate `requirements.md` in the same commit.
- A HOWTO that's more than two weeks stale relative to actual practice is a bug.

See the [documentation index](docs/README.md).
