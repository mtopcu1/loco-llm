# Contributing to LocalLLM

## Commit messages — Conventional Commits

Every commit on `main` follows [Conventional Commits](https://www.conventionalcommits.org/).
This is **not** decoration: `release-please` reads commit messages to decide
when to cut a release and what the next version number is.

### Recognized prefixes

| Prefix         | Version bump (pre-1.0) | Appears in CHANGELOG | Use for |
|----------------|-----------------------|----------------------|---------|
| `feat:`        | minor (0.x → 0.(x+1))  | yes, "Features"      | New CLI commands, wizard steps, runtime presets, flags. |
| `fix:`         | patch (0.x.y → 0.x.(y+1)) | yes, "Bug Fixes"     | Bug fixes. |
| `perf:`        | patch                  | yes, "Performance"   | Measurable performance improvements. |
| `docs:`        | none                   | yes, "Documentation" | Documentation changes that affect users. |
| `feat!:` / `fix!:` / footer `BREAKING CHANGE:` | minor (pre-1.0); will be major post-1.0 | yes, highlighted | Breaking schema/CLI changes. |
| `chore:` `refactor:` `test:` `ci:` `style:` | none | no (hidden) | Internal changes that don't affect users. |

### Examples

```text
feat(serve): add --restart flag to stop+swap configs in one shot
fix(model-pull): retry idempotently when HF returns 429
feat!(config): require explicit serve.host (previously defaulted to 0.0.0.0)

BREAKING CHANGE: existing configs without an explicit `serve.host` will
refuse to start; add `host: 127.0.0.1` (or your previous default) to fix.
```

### What if I forget?

Non-conventional commits are silently ignored by release-please — they
won't break the build, but they also won't show up in the changelog. If
you realize mid-PR, rebase / squash to fix; for PRs with many commits,
use a Conventional-style PR title and ensure "Squash and merge" is the
merge strategy.

## Release flow

**One-time setup:** If `release-please` fails with "not permitted to create … pull requests", follow [docs/RELEASE_SETUP.md](docs/RELEASE_SETUP.md) (enable Actions PR creation, then re-run the workflow).

Releases are fully automated:

1. Merge PRs into `main` using Conventional Commit messages.
2. `release-please` opens (or updates) a single long-lived **release PR**
   that accumulates the changelog and bumps the version in
   `pyproject.toml` and `src/llm_cli/__init__.py`.
3. When ready to release, **review the release PR** (it shows you exactly
   what version + changelog will land) and **merge it**.
4. The merge triggers tag creation, GitHub Release creation, PyPI upload,
   and scaffold-tarball attach. No human action between merge and the
   release going live.

## Dev workflow

Contributors install an **editable** `llm-dev` binary alongside the stable `llm` pipx install. The dev binary reads scaffold assets from your git checkout via `repo_root`.

```bash
git clone https://github.com/mtopcu1/local-llm-scaffold.git
cd local-llm-scaffold
./scripts/install-dev.sh
export PATH="$HOME/.local/bin:$PATH"
llm-dev doctor
```

`install-dev.sh` runs `pipx install --editable . --force --suffix=-dev`, sets `repo_root` to the checkout, and runs `llm-dev setup --default` when no settings file exists yet.

### Try a PR branch

```bash
gh pr checkout 123
./scripts/install-dev.sh
llm-dev <whatever-you-want-to-test>
# when done:
pipx uninstall localllm-cli
```

(`pipx` names the venv `localllm-cli` even when the binary is `llm-dev`.)

Do **not** use `git pull` in a production data directory for updates — end users run `llm update`. For unreleased code, use the dev install above; there is no per-branch PyPI channel.
