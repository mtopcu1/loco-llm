# Installation

LocalLLM installs as a **git checkout** at `LOCO_LLM_HOME` (default `~/.loco-llm`), with an editable Python install in `.venv` and `llm` on your PATH.

## One-line install (recommended)

Inside WSL2, Linux, or macOS (requires `git`, Python 3.11+, `curl`):

```bash
curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"   # if not already
llm setup
```

The script:

1. Installs [uv](https://github.com/astral-sh/uv) if missing.
2. Clones `https://github.com/mtopcu1/loco-llm.git` to `~/.loco-llm` (or updates an existing clone with the same `origin`).
3. Checks out the **latest semver tag** (`v*.*.*`).
4. Creates `.venv` and runs `uv pip install -e .`.
5. Symlinks `~/.local/bin/llm` → `~/.loco-llm/.venv/bin/llm`.

Run `llm doctor` after install to verify prerequisites.

## Installer flags

Pass options to the script when piping through bash:

```bash
curl -fsSL .../scripts/install.sh | bash -s -- --dir /opt/loco-llm
```

| Flag | Purpose |
|------|---------|
| `--dir <path>` | Override `LOCO_LLM_HOME` (default `~/.loco-llm`) |
| `--tag vX.Y.Z` | Pin to a specific release tag |
| `--branch <name>` | Track a branch tip instead of latest tag (testing; warns) |

Environment: `LOCO_LLM_HOME` overrides the default install directory before flags are applied.

## Layout after install

```
~/.loco-llm/                 ← LOCO_LLM_HOME (git clone)
├── .git/
├── .venv/bin/llm
├── runtimes/ configs/ benchmarks/
└── src/llm_cli/

~/.local/bin/llm  →  ~/.loco-llm/.venv/bin/llm

~/.config/localllm/          ← user settings (unchanged by install)
~/.local/share/localllm/     ← runtime state, models, builds
```

User data paths are **not** removed or migrated by the installer. Settings from a prior install carry over.

## Upgrading from pipx / PyPI

The project no longer publishes wheels to PyPI. One-time cleanup:

```bash
pipx uninstall loco-llm-cli || true
rm -f ~/.local/bin/llm
curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
```

## Upgrading from an old git clone at `~/local-llm-scaffold`

Use the curl installer above (fresh `~/.loco-llm`) or point `LOCO_LLM_HOME` at your checkout and run `llm update`. There is no `migrate-from-v0.2.sh` in the new model.

## Related

- [UPDATE.md](UPDATE.md) — day-to-day upgrades via `llm update`
- [DEVELOPMENT.md](DEVELOPMENT.md) — contributor install from a feature branch
- [wsl-setup.md](wsl-setup.md) — WSL2 + systemd + GPU drivers
