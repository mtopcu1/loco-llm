# Glossary

Quick links to terms used across loco-llm docs. Anchors match GitHub heading slugs.

## Paths and layout

| Term | Meaning | More |
|------|---------|------|
| [LOCO_HOME / data home](#paths-and-layout) | User data root: `config.yaml`, `configs/`, `models/`, `runtimes/`, `cache/`, `state/`. Default `~/.loco`. | [INSTALLATION.md](INSTALLATION.md), [ARCHITECTURE.md](ARCHITECTURE.md) |
| [LOCO_INSTALL / install root](#paths-and-layout) | Git clone + `.venv` + upstream `runtimes/` recipes. Default `~/.loco/install`. | [INSTALLATION.md](INSTALLATION.md) |
| [config.yaml](#paths-and-layout) | Machine settings (paths only). Not a launch config. | [CLI.md](CLI.md#setup-and-settings), [repo-conventions.md](repo-conventions.md) |
| [Launch config](#launch-config) | One serve unit: `configs/<id>.yaml` under the data home. | [add-a-config.md](add-a-config.md) |
| [repo_root](#paths-and-layout) | Optional dev override: use a git checkout instead of only `LOCO_INSTALL` recipes. | `loco settings edit repo_root` |

## Runtime and model

| Term | Meaning | More |
|------|---------|------|
| [Runtime](#runtime-and-model) | A backend (e.g. `llamacpp`, `stub-runtime`): manifest + build/serve scripts. | [add-a-runtime.md](add-a-runtime.md) |
| [Preset runtime](#runtime-and-model) | Official runtime installed via `loco runtime install` into `{data_root}/runtimes/<id>/`. | [runtime-lifecycle.md](runtime-lifecycle.md) |
| [Custom runtime](#runtime-and-model) | User-authored recipe under `{data_root}/user/runtimes/<id>/`. | [add-a-runtime.md](add-a-runtime.md) |
| [Model registry](#runtime-and-model) | `{data_root}/models/registry.json` + per-model directories. | [add-a-model.md](add-a-model.md) |
| [Build params](#runtime-and-model) | Install-time options (e.g. `build.flavor: cuda`) stored in `.installed`. | Runtime manifest `build:` section |

## CLI workflows

| Term | Meaning | More |
|------|---------|------|
| [Setup chain](#cli-workflows) | `loco setup` steps: runtime → model pull → config → serve → optional dashboard. | [CLI.md](CLI.md#setup-and-settings), [wizards.md](wizards.md) |
| [Doctor](#cli-workflows) | External prerequisite checks; hints only, no auto-install. | [CLI.md](CLI.md#doctor), [requirements.md](../requirements.md) |
| [Pre-flight](#cli-workflows) | Runtime `requires:` checks before `runtime install` (same hint style as doctor). | Runtime manifests |
| [Serve modes](#cli-workflows) | Foreground, background, or systemd for `loco serve`. | [lifecycle.md](lifecycle.md) |

## Dashboard

| Term | Meaning | More |
|------|---------|------|
| [Dashboard](#dashboard) | Optional FastAPI + static UI; reads/writes the same files as the CLI. | [DASHBOARD.md](DASHBOARD.md) |
| [Dashboard scope](#dashboard) | Node/npm requirements in `requirements.yaml` (`scope: dashboard`). | `loco doctor --scope dashboard` |

## Install and release

| Term | Meaning | More |
|------|---------|------|
| [Release tag](#install-and-release) | Semver `v*.*.*` on `main`; default for `install.sh` and `loco update`. | [UPDATE.md](UPDATE.md), [RELEASE.md](RELEASE.md) |
| [Re-anchor](#install-and-release) | `loco update --stable` switches to the latest release tag (e.g. after `--branch`). | [UPDATE.md](UPDATE.md) |

## Repository (contributors)

| Term | Meaning | More |
|------|---------|------|
| [Scaffold / recipes](#repository-contributors) | In-repo `runtimes/`, `configs/` examples, `benchmarks/` — copied or merged at runtime. | [repo-conventions.md](repo-conventions.md) |
| [requirements.yaml](#repository-contributors) | Source of truth for doctor checks; regenerate `requirements.md` when changed. | [CONTRIBUTING.md](../CONTRIBUTING.md#documentation-discipline) |
