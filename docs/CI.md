# Continuous integration

GitHub Actions runs **three workflows** on pull requests to `main` on `github.com/mtopcu1/loco-llm`.

## `ci.yml` — full Python test suite

| Setting | Value |
|---------|--------|
| Trigger | `pull_request` to `main` only (no push-to-main matrix) |
| Job name | `pytest` |
| Skip | PRs whose head branch starts with `release-please--` |
| Runner | `ubuntu-latest` |
| Tooling | `astral-sh/setup-uv@v3`, Python 3.11, `uv pip install -e ".[dev,dashboard]"`, `uv run pytest -q --tb=short` |

## `dashboard-tests.yml` — dashboard unit tests and frontend pipeline

| Setting | Value |
|---------|--------|
| Trigger | `pull_request` when dashboard / webapi / related paths change |
| Job name | `dashboard` |
| Runner | `ubuntu-latest` |
| Steps | Targeted pytest (`test_core_dashboard`, `test_core_disk`, `test_cli_dashboard`), then `npm ci`, typecheck, test, build, bundle-size check |

## `api-contract-check.yml` — OpenAPI client drift

| Setting | Value |
|---------|--------|
| Job name | `check` |
| Purpose | Regenerated `dashboard/src/api/generated.ts` matches the FastAPI schema |

Use **distinct job names** so GitHub does not register two checks both called `test` (that collides with branch protection and makes PR status ambiguous).

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

- **Required status checks:** `pytest`, `dashboard`, and `check` (job names from the workflows above)
- **Admin bypass:** enabled so release PRs from `github-actions[bot]` can merge when GitHub does not attach checks to bot-opened PRs

Do **not** require a single ambiguous context `test` (two workflows used that name and fought on PR #31). Do **not** require the old contexts `test (3.11)`, `test (3.12)`, or `build-check`.

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
