# Installation

loco-llm uses a **Hermes-style nested layout**: user data at `~/.loco`, git checkout at `~/.loco/install`.

## One-line install (recommended)

Inside WSL2, Linux, or macOS (requires `git`, Python 3.11+, `curl`):

```bash
curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"   # if not already
loco doctor
```

The script:

1. Installs [uv](https://github.com/astral.sh/uv) if missing.
2. Clones `https://github.com/mtopcu1/loco-llm.git` to `~/.loco/install`.
3. Checks out the **latest semver tag** (`v*.*.*`).
4. Creates `.venv` and runs `uv pip install -e .`.
5. Symlinks `~/.local/bin/loco` → `~/.loco/install/.venv/bin/loco`.
6. Creates `~/.loco/config.yaml`, `configs/`, `models/`, `runtimes/`, `cache/`, `state/`.
7. Seeds example launch configs from the repo into `~/.loco/configs/` (skip existing).
8. Prints next steps: `loco setup` (first-run wizard) and `loco doctor`.

## Installer flags

```bash
curl -fsSL .../scripts/install.sh | bash -s -- --data-home /opt/loco-data
```

| Flag | Purpose |
|------|---------|
| `--data-home <path>` | User data root (default `~/.loco`) |
| `--dir <path>` | Git install root (default `$DATA_HOME/install`) |
| `--tag vX.Y.Z` | Pin to a specific release tag |
| `--branch <name>` | Track a branch tip instead of latest tag (testing) |

Environment:

| Variable | Purpose |
|----------|---------|
| `LOCO_HOME` | Data home (config, configs, models, builds) |
| `LOCO_INSTALL` | Git install root (code + upstream recipes) |

Deprecated (still read): `LOCO_LLM_DATA`, `LOCO_LLM_HOME`.

## Layout after install

```text
~/.loco/                          ← LOCO_HOME
├── config.yaml                   ← machine settings (paths)
├── configs/*.yaml                ← launch units (canonical; seeded at install)
├── models/ runtimes/ cache/ state/
├── user/runtimes/                ← custom runtime recipes (optional)
└── install/                      ← LOCO_INSTALL (git clone)
    ├── .git/ .venv/ src/
    ├── runtimes/ benchmarks/     ← upstream recipes (read-only to you)
    └── configs/                  ← examples only; copied to ../configs/ once

~/.local/bin/loco  →  ~/.loco/install/.venv/bin/loco
```

`loco update` only updates `install/`. Your configs and artifacts under `~/.loco/` are never touched by git.

## Reinstall (clean slate)

```bash
pipx uninstall loco-llm-cli 2>/dev/null || true
rm -f ~/.local/bin/llm ~/.local/bin/loco
rm -rf ~/.loco ~/.loco-llm ~/.config/llm
curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
```

## Related

- [UPDATE.md](UPDATE.md) — day-to-day upgrades via `loco update`
- [DEVELOPMENT.md](DEVELOPMENT.md) — contributor install from a feature branch
- [wsl-setup.md](wsl-setup.md) — WSL2 + systemd + GPU drivers
- [Hermes layout spec](superpowers/specs/2026-05-20-hermes-layout-and-branding-design.md)
