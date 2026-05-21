# Updating

End-user upgrades run through **`loco update`**, which operates on the git checkout at `LOCO_INSTALL` (see [INSTALLATION.md](INSTALLATION.md)).

## Default: refresh current ref

```bash
loco update
```

Behavior depends on what is checked out in `LOCO_INSTALL`:

| Current HEAD | What `loco update` does |
|--------------|-------------------------|
| **Branch** | `git fetch` + `git pull --ff-only` on that branch, then sync Python deps |
| **Release tag** | Move to the latest `v*.*.*` tag if behind, else sync deps only |
| **Detached commit** | Sync deps only (does not move the checkout) |

If you installed with `--branch feat/…`, bare `loco update` **stays on that branch** and pulls its latest tip.

## Flags

| Command | Behavior |
|---------|----------|
| `loco update --check` | Print current vs. latest tag; exit **1** if behind (no changes) |
| `loco update --branch <name>` | Switch to a branch and `git pull --ff-only` |
| `loco update --tag vX.Y.Z` | Pin to a specific tag (rollback or testing) |
| `loco update --stable` | Switch to the latest release tag (leave a feature branch) |
| `loco update --restart` | Stop a running service before update, re-serve afterward |

`--branch`, `--tag`, `--check`, and `--stable` are mutually exclusive.

## Hotfix workflow

```bash
loco update --branch hotfix/scaffold-perms
# ... test ...
loco update              # stays on hotfix/scaffold-perms, pulls new commits

# When a release tag exists and you want stable again:
loco update --stable
```

## Service running

If a config is served, `loco update` refuses unless you `loco stop` first or pass `--restart`.

## Refusal cases

- `LOCO_INSTALL` is not a git clone → reinstall via the [curl installer](INSTALLATION.md).
- `origin` is not `github.com/mtopcu1/loco-llm` → intentional guard; fix remote or reinstall.
- No semver tags on origin (when a tag/stable update is needed) → use `--branch <name>` instead.

## Visibility

- `loco --version` — package version; appends `(branch: …)` or `(detached: …)` when HEAD is not an exact tag.
- `loco doctor` — **install-channel** check warns when not on a release tag; run `loco update --stable` to move to the latest tag.

## Developers

Contributors working in a git clone use `git pull` and `uv pip install -e ".[dev]"` — not `loco update` against a separate `LOCO_INSTALL`. See [DEVELOPMENT.md](DEVELOPMENT.md).
