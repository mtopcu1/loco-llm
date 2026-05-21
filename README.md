# loco-llm

Personal control plane for local LLM runtimes: install runtimes, pull models, define launch configs, and serve them with `loco serve`.

The git repo holds **recipes and CLI code** only. Weights and build artifacts live under your data home (`~/.loco` by default). See [Architecture](docs/ARCHITECTURE.md).

## Install

Official installer (WSL2, Linux, or macOS — needs `git`, Python 3.11+, `curl`):

```bash
curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
```

By default this checks out the **latest release tag** into `~/.loco/install`, creates `~/.loco/config.yaml`, and seeds example configs.

**Pin a release, branch, or commit** (pass args after `bash -s --`):

```bash
curl -fsSL .../install.sh | bash -s -- --tag v0.2.0
curl -fsSL .../install.sh | bash -s -- --branch feat/my-fix
curl -fsSL .../install.sh | bash -s -- --commit abc1234
curl -fsSL .../install.sh | bash -s -- --data-home /opt/loco --dir /opt/loco/install
```

Use only one of `--tag`, `--branch`, or `--commit`. Default: latest release tag.

Details: [Installation](docs/INSTALLATION.md). Day-to-day upgrades: [Update](docs/UPDATE.md) (`loco update`, `loco update --tag`, `loco update --branch`).

## First run

```bash
loco doctor          # check tools on your machine (hints only — you install)
loco setup           # wizard: runtime → model → config → optional serve
```

Paths and overrides: `loco settings show` / `loco settings edit <key>`. Not part of `loco setup`.

## Dependencies

`loco doctor` verifies external tools from [`requirements.yaml`](requirements.yaml) (Python, `git`, `hf` CLI, build tools, optional Node for the dashboard). **Loco does not install them for you** — it prints hints (`pip install …` when PyPI applies, otherwise official download links).

Runtime-specific tools (e.g. `cmake`, CUDA `nvcc`) appear when you install that runtime or run `loco doctor --runtime llamacpp`. Human-readable list: [`requirements.md`](requirements.md).

GPU / WSL2 one-time host setup: [wsl-setup.md](docs/wsl-setup.md).

## Dashboard (optional)

Browser UI for configs, runtimes, logs, and doctor results — same files as the CLI, no separate state.

```bash
loco dashboard install
loco dashboard serve
```

Requires Node 20+ (see doctor hints). Security and remote access: [DASHBOARD.md](docs/DASHBOARD.md), [DASHBOARD-SECURITY.md](docs/DASHBOARD-SECURITY.md).

## CLI reference

Full command list, flags, and examples: **[docs/CLI.md](docs/CLI.md)**.

Quick smoke without GPU weights:

```bash
loco runtime install stub-runtime --yes
loco serve stub-runtime__default
```

## Docs

| Topic | Link |
|-------|------|
| Glossary (fast navigation) | [docs/GLOSSARY.md](docs/GLOSSARY.md) |
| All documentation | [docs/README.md](docs/README.md) |
| Contributing & doc discipline | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Develop from a git clone | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
