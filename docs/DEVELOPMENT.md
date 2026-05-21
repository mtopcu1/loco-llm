# Development

How to hack on LocalLLM from a git clone. End-user install/update docs: [INSTALLATION.md](INSTALLATION.md), [UPDATE.md](UPDATE.md).

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- `git`

WSL2 is the primary target for runtime work; see [wsl-setup.md](wsl-setup.md).

## Dev install

```bash
git clone https://github.com/mtopcu1/loco-llm.git
cd loco-llm
uv venv && uv pip install -e ".[dev]"
uv run pytest -q
uv run loco --version
```

There is **no** `scripts/install-dev.sh` — use `uv` directly.

### Use this checkout as the runtime install root

Either:

```bash
export LOCO_LLM_HOME="$(pwd)"
```

or set `repo_root` in `loco settings` to your clone path. Then `loco` resolves `runtimes/` from the working tree.

### Try a PR branch

```bash
gh pr checkout 123
uv pip install -e ".[dev]"
uv run loco doctor
```

Use `git pull` + `uv pip install -e ".[dev]"` while iterating — **not** `loco update` (that targets `LOCO_LLM_HOME` managed installs).

### Git worktrees

If you use `git worktree add` for parallel branches, **remove the worktree before deleting its directory**, then reinstall the editable CLI from the checkout you keep:

```bash
git worktree remove .worktrees/my-branch
pip install -e ".[dev]"   # or: uv pip install -e ".[dev]"
loco doctor --quick
```

`loco doctor` reports a broken editable target when pip still points at a missing path (common after deleting a worktree folder without reinstalling).

For arrow-key wizards in automation or MCP terminals, use numbered prompts (default on Windows consoles without Windows Terminal) or set `LLM_PLAIN_WIZARDS=1`. Set `LLM_FORCE_QUESTIONARY=1` to force arrow menus.

## Running the CLI

```bash
uv run loco setup --default
uv run loco doctor
uv run pytest -q
```

Optional: `source .venv/bin/activate` and call `loco` directly.

## Commits and releases

Follow [Conventional Commits](../CONTRIBUTING.md). `release-please` drives version bumps; merging the release PR creates the tag users receive via `loco update`.

## Related

- [CONTRIBUTING.md](../CONTRIBUTING.md) — PR workflow
- [CI.md](CI.md) — what runs on GitHub Actions
- [repo-conventions.md](repo-conventions.md) — layout and discovery rules
