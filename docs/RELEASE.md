# Releases

Releases are **git tags** plus GitHub Releases with CHANGELOG text. Users pick up new versions with `loco update` (see [UPDATE.md](UPDATE.md)).

## Maintainer flow

1. Land features on `main` with [Conventional Commits](../CONTRIBUTING.md).
2. `release-please.yml` opens or updates a **release PR** (version bump in `pyproject.toml`, `src/llm_cli/__init__.py`, and `CHANGELOG.md`).
3. Review the release PR and **merge** (admin bypass is OK — bot PRs often lack CI checks).
4. Merging creates tag `vX.Y.Z` and a GitHub Release.
5. Users run `loco update` to fetch and checkout the new tag.

One-time GitHub setup: [RELEASE_SETUP.md](RELEASE_SETUP.md).

## Versioning (pre-1.0)

| Commit type | Bump |
|-------------|------|
| `feat:` | minor |
| `fix:`, `perf:` | patch |
| `feat!:` / `BREAKING CHANGE:` | minor (major after 1.0) |
| `docs:`, `chore:`, `ci:`, … | none (changelog hidden) |

`release-please` reads commit messages since the last release; non-conventional merge titles are ignored.

## PyPI (removed)

**PyPI publishing was removed** in the git-tag distribution model (2026-05).

Previously the project attempted:

- `pipx install loco-llm-cli` from PyPI
- A separate scaffold tarball on GitHub Releases
- `publish.yml` / publish jobs chained off release-please

That stack is gone. There is no wheel upload, no trusted publisher, and no scaffold asset split. The install root **is** the git clone at `LOCO_LLM_HOME`; `runtimes/`, `configs/`, and `benchmarks/` update with the same tag as the CLI.

Optional cleanup on PyPI: yank or deprecate reserved names (`loco-llm-cli`, etc.) and delete trusted-publisher entries — see plan Task 11 in `docs/superpowers/plans/2026-05-19-git-tag-distribution.md`.

## CI at release time

- **Feature PRs** — `ci.yml` runs `test` on pull requests to `main`.
- **Merge to main** — `release-please.yml` only; no full pytest re-run on every push.
- **Release PR merge** — tag + GitHub Release; no publish job.

Details: [CI.md](CI.md).

## Design reference

Full rationale: `docs/superpowers/specs/2026-05-19-git-tag-distribution-design.md`.
