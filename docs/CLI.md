# CLI reference

All commands use the `loco` entry point (`~/.local/bin/loco` after install). Run `loco --help` or `loco <group> --help` for live options.

Settings file: `{LOCO_HOME}/config.yaml` (default `~/.loco/config.yaml`). See [GLOSSARY.md](GLOSSARY.md) for path terms.

## Setup and settings

| Command | Purpose |
|---------|---------|
| `loco setup` | First-run wizard chain: runtime → HF model URL → launch config → optional background serve → optional dashboard install. Requires install.sh bootstrap (`config.yaml` + `data_root`). Yes/No steps use **No / Yes** buttons (←→, Y/N, Enter). |
| `loco settings show` | Print settings path, stored YAML, and resolved directories. |
| `loco settings edit <key>` | Interactive edit of one key (`data_root`, `repo_root`, `runtimes_dir`, …). |
| `loco settings edit <key> --default` | Reset `data_root` to built-in default, or remove override for derived dir keys. |
| `loco settings env` | Print `export` lines for shell scripts (`eval "$(loco settings env)"`). |

## Install and upgrade

| Command | Purpose |
|---------|---------|
| `loco update` | Fetch and checkout latest release tag in `LOCO_INSTALL`; reinstall editable package. |
| `loco update --check` | Report current vs available version; no changes. |
| `loco update --tag vX.Y.Z` | Pin install checkout to a tag. |
| `loco update --branch <name>` | Track a branch tip (testing). |
| `loco update --restart` | After upgrade, restart running serve/dashboard if applicable. |

Installer flags (`--tag`, `--branch`, `--data-home`, `--dir`): [INSTALLATION.md](INSTALLATION.md).

## Doctor

| Command | Purpose |
|---------|---------|
| `loco doctor` | Check universal requirements + installed runtimes; print install hints. |
| `loco doctor --quick` | Fast sanity check (settings, scaffold, requirements file). |
| `loco doctor --runtime <id>` | Include that runtime's `requires:` (respects stored build params). |
| `loco doctor --all` | All runtime manifests, not only installed. |
| `loco doctor --scope dashboard` | Node/npm, dashboard build, server PID. |
| `loco doctor render-requirements` | Regenerate `requirements.md` from YAML (contributors). |

Loco **does not** auto-install missing tools.

## Runtime

| Command | Purpose |
|---------|---------|
| `loco runtime setup` | Interactive wizard: official preset install or custom runtime recipe. |
| `loco runtime list` | List discovered runtimes and install state. |
| `loco runtime info <id>` | Manifest path, `.installed` record, drift hints. |
| `loco runtime install <id>` | Build/install; `--yes` for defaults; `-p key=value` build params. |
| `loco runtime rebuild <id>` | Reinstall with stored params; `--reset` to re-prompt. |
| `loco runtime uninstall <id>` | Remove install marker; `--purge` deletes artifacts. |

Pre-flight checks run on install and print hints from the runtime manifest.

## Model

| Command | Purpose |
|---------|---------|
| `loco model list` | Registered models (`registry.json`). |
| `loco model info <id>` | Full registry entry. |
| `loco model pull <url-or-id>` | Hugging Face download; `--id`, `--force`, include/exclude globs. |
| `loco model add <id> <path> --format <fmt>` | Register local weights (symlink or copy). |
| `loco model uninstall <id>` | Remove registry entry; `--purge` deletes files. |

## Config

| Command | Purpose |
|---------|---------|
| `loco config setup` | Interactive launch config wizard (recommendations + review). |
| `loco config new` | Non-interactive YAML: `--runtime`, `--model`, `--param k=v`, `--force`. |
| `loco config show <id>` | Print one config (paths expanded). |
| `loco config validate` | Validate all configs under the data home. |

Launch configs live in `{data_root}/configs/*.yaml`.

## Serve and lifecycle

| Command | Purpose |
|---------|---------|
| `loco serve <config-id>` | Start config (background default); `--foreground`, `--systemd`. |
| `loco switch <config-id>` | Stop current + start new in the same mode. |
| `loco stop` | Stop the running service. |
| `loco status [--json]` | Running config, mode, port, uptime. |
| `loco logs [-f] [-n N]` | Tail file or journald logs. |

Details: [lifecycle.md](lifecycle.md).

## Dashboard

| Command | Purpose |
|---------|---------|
| `loco dashboard` | Alias for `loco dashboard serve`. |
| `loco dashboard install` | Python deps + `npm ci && build`; `--reset`, `--skip-python`, `--skip-frontend`. |
| `loco dashboard serve` | Local server (default background); `--port`, `--foreground`, `--no-open`. |
| `loco dashboard status` | Install marker and server PID. |
| `loco dashboard stop` | Stop dashboard process. |
| `loco dashboard uninstall` | Remove install marker; `--purge` drops `dist/` and `node_modules/`. |

Overview: [DASHBOARD.md](DASHBOARD.md).

## Discovery and advice

| Command | Purpose |
|---------|---------|
| `loco list` | Summary of runtimes, models, configs, benchmarks. |
| `loco advisor` | VRAM-aware param hints (interactive or `--runtime` + `--model` or config id; `--json`). |
| `loco specs` | Regenerate auto block in `specs.md`. |
| `loco specs --check` | Exit nonzero if `specs.md` is stale. |
| `loco specs --print` | Print detection without writing. |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `LOCO_HOME` | Data home (`config.yaml`, configs, models, runtimes, state). |
| `LOCO_INSTALL` | Git checkout + venv (upstream recipes). |
| `LOCO_LLM_DATA`, `LOCO_LLM_HOME` | Deprecated aliases (still read). |

## Related HOWTOs

- [add-a-runtime.md](add-a-runtime.md)
- [add-a-model.md](add-a-model.md)
- [add-a-config.md](add-a-config.md)
- [wizards.md](wizards.md)
