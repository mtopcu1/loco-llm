# Updating

End-user upgrades run through **`loco update`**, which operates on the git checkout at `LOCO_INSTALL` (see [INSTALLATION.md](INSTALLATION.md)).

## Default: latest stable tag

```bash
loco update
```

1. `git fetch --tags --prune origin`
2. If you are on a **branch**, warns and **re-anchors** to the highest `v*.*.*` tag.
3. If already on that tag, prints "already on latest stable" and exits.
4. Stashes dirty working trees, checks out the tag, runs `uv pip install -e .` to sync deps.

Bare `loco update` always returns you to the latest release tag — it does not leave you on `main` or a hotfix branch.

## Flags

| Command | Behavior |
|---------|----------|
| `loco update --check` | Print current vs. latest tag; exit **1** if behind (no changes) |
| `loco update --branch <name>` | Checkout branch tip and `git pull --ff-only`; warns you are off stable |
| `loco update --tag vX.Y.Z` | Pin to a specific tag (rollback or testing) |
| `loco update --restart` | Stop a running service before update, re-serve afterward |

`--branch`, `--tag`, and `--check` are mutually exclusive.

## Hotfix workflow

```bash
# Maintainer pushes hotfix/scaffold-perms
loco update --branch hotfix/scaffold-perms
# ... test ...

# After release-please tags v0.4.2:
loco update
# re-anchors to v0.4.2
```

## Service running

If a config is served, `loco update` refuses unless you `loco stop` first or pass `--restart`.

## Refusal cases

- `LOCO_INSTALL` is not a git clone → reinstall via the [curl installer](INSTALLATION.md).
- `origin` is not `github.com/mtopcu1/loco-llm` → intentional guard; fix remote or reinstall.
- No semver tags on origin → use `--branch main` only if you intend to track untagged work.

## Visibility

- `loco --version` — package version; appends `(branch: …)` or `(detached: …)` when HEAD is not an exact tag.
- `llm doctor` — **install-channel** check warns when not on a release tag; run `loco update` to re-anchor.

## Developers

Contributors working in a git clone use `git pull` and `uv pip install -e ".[dev]"` — not `loco update` against a separate `LOCO_INSTALL`. See [DEVELOPMENT.md](DEVELOPMENT.md).
