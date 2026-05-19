# Release automation setup (one-time)

`release-please` failed on `main` with:

```text
GitHub Actions is not permitted to create or approve pull requests.
```

The workflow **did** prepare a release branch (`release-please--branches--main--components--loco-llm-cli`) with version **0.3.0** and `CHANGELOG.md`. Only opening the release **pull request** was blocked.

## 1. Enable Actions to open PRs (required)

In GitHub: **Settings → Actions → General → Workflow permissions**

1. Select **Read and write permissions** (recommended default for this repo).
2. Enable **Allow GitHub Actions to create and approve pull requests**.
3. Save.

Or with `gh` (repo admin):

```bash
gh api repos/mtopcu1/local-llm-scaffold/actions/permissions/workflow \
  -X PUT \
  -f default_workflow_permissions=write \
  -F can_approve_pull_request_reviews=true
```

Then confirm the checkbox above is still enabled in the UI (some org policies require both).

## 2. Re-run release-please

After step 1, either:

**Option A — Re-run the failed workflow**

```bash
gh run rerun 26068828647 --repo mtopcu1/local-llm-scaffold
```

Or **Actions → release-please → Run workflow** (uses `workflow_dispatch` on `main`).

**Option B — Open the release PR manually** (if the branch already exists)

```bash
gh pr create \
  --repo mtopcu1/local-llm-scaffold \
  --head release-please--branches--main--components--loco-llm-cli \
  --base main \
  --title "chore(main): release 0.3.0" \
  --body "Release PR prepared by release-please. Review CHANGELOG and version bumps, then merge."
```

## 3. PyPI trusted publishing (before first real release)

When you merge the release PR, `publish.yml` runs on `release: published`.

1. [pypi.org](https://pypi.org) → **Publishing** → add trusted publisher:
   - Owner: `mtopcu1`
   - Repository: `local-llm-scaffold`
   - Workflow: `publish.yml`
   - Environment: (leave empty unless you use one)
2. Register the project name `loco-llm-cli` on PyPI if not already claimed.

## 4. Expected flow after setup

```mermaid
flowchart LR
  merge[Merge to main] --> rp[release-please.yml]
  rp --> pr[Release PR]
  pr --> mergeRP[Merge release PR]
  mergeRP --> tag[Tag + GitHub Release]
  tag --> pub[publish.yml]
  pub --> pypi[PyPI wheel/sdist]
  pub --> assets[scaffold tarball on Release]
```

## 5. Commit message warnings (normal)

Logs may show `commit could not be parsed` for merge commits (`Merge pull request #…`) or old non-conventional messages. Those commits are **skipped**; `feat:` / `fix:` commits since `0.2.0` still drive the **0.3.0** bump.
