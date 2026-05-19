# Continuous integration

GitHub Actions runs **two workflows** on `github.com/mtopcu1/loco-llm`.

## `ci.yml` — tests on pull requests

| Setting | Value |
|---------|--------|
| Trigger | `pull_request` to `main` only (no push-to-main matrix) |
| Job name | `test` |
| Skip | PRs whose head branch starts with `release-please--` |
| Runner | `ubuntu-latest` |
| Tooling | `astral-sh/setup-uv@v3`, Python 3.11, `uv pip install -e ".[dev]"`, `uv run pytest` |

Feature work must pass this job before merge. The required status check on `main` should be **`test`** (single context).

## `release-please.yml` — versioning and tags

| Setting | Value |
|---------|--------|
| Trigger | `push` to `main`, `workflow_dispatch` |
| Jobs | `release-please` only |
| Permissions | `contents: write`, `pull-requests: write` (no `id-token` — no PyPI) |
| Action | `googleapis/release-please-action@v4` |

Opens or updates the release PR. Merging it creates `vX.Y.Z` and a GitHub Release. **No publish job**, no wheel build, no scaffold tarball upload.

## Branch protection

Configure `main` with:

- **Required status check:** `test` (from `ci.yml`)
- **Admin bypass:** enabled so release PRs from `github-actions[bot]` can merge when GitHub does not attach checks to bot-opened PRs

Do **not** require the old contexts `test (3.11)`, `test (3.12)`, or `build-check` — those jobs were removed with the git-tag distribution change.

See [RELEASE_SETUP.md](RELEASE_SETUP.md) for one-time GitHub settings.

## Local parity

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest -q --tb=short
```

Matches what CI runs.

## Related

- [RELEASE.md](RELEASE.md) — what happens when the release PR merges
- [DEVELOPMENT.md](DEVELOPMENT.md) — local dev install
