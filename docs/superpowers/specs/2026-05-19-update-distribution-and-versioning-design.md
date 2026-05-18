# LocalLLM Update, Distribution & Versioning Design

_Date: 2026-05-19_
_Status: Drafted, awaiting user review_
_Scope: Distribution channel, self-update mechanism, asset-layer split, and release/versioning automation. Migration from the current v0.2.0 editable-clone model to v0.3.0 distributed model._

## 1. Purpose

Make LocalLLM installable, updatable, and versioned the way a small public CLI should be: one command to install, one command to update, automatic versioning from commits, and a clean dev workflow that doesn't fight the published one.

## 2. Problem

Today's install/update story is a manual git workflow:

- Fresh install: clone the repo, `./install.sh`, edit settings.
- Update: `cd ~/local-llm-scaffold && git pull && ...` — no `llm update`.
- Versioning: `pyproject.toml` and `src/llm_cli/__init__.py` are edited by hand; there are no git tags.
- The repo doubles as the **asset library** — `runtimes/`, `configs/`, `benchmarks/` are read at runtime from `repo_root`. User-authored custom runtimes (via `llm runtime setup --kind custom`) and configs land in the same tree, so `git pull` risks conflicting with user customizations.
- No published artifacts; no PyPI presence; no GitHub release surface.

This is acceptable for a personal tool but not for the "public CLI like hermes/opencode" audience the maintainer has chosen to target.

## 3. Goals

1. **Single-command install** for new users (`curl|bash` or `pipx install`).
2. **Single-command update** (`llm update`) that atomically refreshes both the CLI and the asset tree.
3. **Asset tree separated from user customizations.** `git pull`-equivalent on the asset tree must never clobber user-authored content.
4. **Automatic versioning** driven by Conventional Commits, with a human-gated release PR.
5. **Tagged releases only**; no per-branch pre-release artifacts (per user choice).
6. **Dev workflow unchanged in spirit.** Maintainers and contributors still run an editable install from a local checkout.
7. **Lossless migration** from v0.2.0 layout to v0.3.0 layout, with a dry-run-first script.

## 4. Non-goals

- No compile-to-binary step (no PyInstaller / PyOxidizer / Bun-compile). Pure-Python `typer` CLI ships as a wheel via pipx. Escape hatch left open for `shiv` later if demand appears.
- No Homebrew tap, no Docker image, no npm postinstall hack, no Windows-native install path. WSL2 / Linux stays the supported environment.
- No PyPI pre-release index usage; no `--channel edge`; no per-branch published wheels.
- No `--branch <name>` flag on `llm update`. Branch testing is a dev-clone concern.
- No automatic rollback of the wheel (one-liner via `pipx install ==<prev>` is documented instead). Scaffold rollback on failure is automatic.
- No "compatibility mode" preserving the v0.2.0 layout. The migration script flips the user to the new layout in one shot.
- No third asset layer (system-wide `/etc/...`) until someone asks for one.
- Release tooling is a single-package monorepo config; no per-subpackage versioning.

## 5. Decisions (Q&A trail)

These were settled during the brainstorming session, in order:

| Question | Decision |
|---|---|
| Audience | Public CLI, hermes/opencode-grade polish. Multi-OS eventually; WSL2/Linux first. |
| Asset strategy | **Two-track**: PyPI wheel for code, sparse git checkout for assets. Maintainer's call after evaluating bundling and editable-forever alternatives. |
| Versioning model | **Conventional Commits + release-please**, with a long-lived release PR as the human gate. |
| Branch builds | **Not published.** Branch testing happens via editable dev installs only. |

## 6. Architecture overview

After this design lands, a normal user's machine looks like:

```
~/.local/bin/llm                            (pipx shim)
~/.local/pipx/venvs/localllm-cli/           (pipx-managed venv with the wheel)
~/.local/share/localllm/scaffold/           (sparse git clone, read-only to the CLI)
  ├── runtimes/{id}/                        (manifests + shell scripts)
  ├── configs/{id}.yaml
  ├── benchmarks/{id}/
  └── requirements.yaml
~/llm/                                      ($LLM_DATA_ROOT)
  ├── runtimes/                             (per-install state — unchanged)
  ├── models/                               (model weights — unchanged)
  ├── cache/                                (HF cache, etc. — unchanged)
  └── user/                                 (NEW — user-authored content)
      ├── runtimes/<custom-id>/
      └── configs/<user-id>.yaml
~/.config/llm/config.yaml                   (settings — unchanged path, repo_root now optional)
```

A maintainer/contributor's machine additionally has:

```
~/dev/local-llm-scaffold/                   (their checkout)
~/.local/pipx/venvs/localllm-cli-dev/       (editable install, `llm-dev` binary)
~/.config/llm/config.yaml                   (with repo_root set to the checkout)
```

The stable `llm` and the dev `llm-dev` coexist on the same machine without conflict.

## 7. Section 1 — Distribution & install UX

### 7.1 One-line install

```bash
curl -fsSL https://raw.githubusercontent.com/mtopcu1/local-llm-scaffold/main/scripts/install.sh | bash
```

`scripts/install.sh` is small and deterministic. It:

1. Verifies prerequisites: `python3 >= 3.11`, `git`, `curl`.
2. Bootstraps `pipx` if missing: `python3 -m pip install --user pipx && python3 -m pipx ensurepath`.
3. Runs `pipx install 'localllm-cli==X.Y.Z'`, where `X.Y.Z` is the release the script ships in (pinned at release time so the script and the tag are in lockstep).
4. Runs `llm update --scaffold-only --yes` to initialize the sparse-checkout scaffold at the matching tag in `$LLM_SCAFFOLD_DIR`.
5. Drops the user into `llm setup` for first-time machine config.

### 7.2 Alternative install for pipx-savvy users

```bash
pipx install localllm-cli
llm setup       # bootstraps scaffold + settings on first run
```

`llm setup`'s first-run logic gains a small responsibility: if `$LLM_SCAFFOLD_DIR` does not exist yet, run `llm update --scaffold-only --yes` as part of setup.

### 7.3 Distribution channel

PyPI only, via standard Python wheel + sdist. No Homebrew / Docker / npm at v0.3.0. Adding a Homebrew tap later via `homebrew-pypi-poet` is a one-liner if demand appears.

### 7.4 Existing `install.sh` becomes the dev installer

The current root-level `install.sh` is renamed to `scripts/install-dev.sh`. Its behavior is rewritten to:

```bash
pipx install --editable . --force --suffix=-dev
llm-dev settings edit repo_root <pwd>
llm-dev setup
```

This is documented in `CONTRIBUTING.md` (new) as the only supported way to "run a branch."

## 8. Section 2 — Layered asset model

### 8.1 Two roots, read in order

| Layer | Path | Owned by | Writable by CLI? |
|---|---|---|---|
| `scaffold` | `$LLM_SCAFFOLD_DIR` (default `~/.local/share/localllm/scaffold/`) | `llm update` | **No.** Treated read-only. |
| `user` | `$LLM_DATA_ROOT/user/` (default `~/llm/user/`) | the user / `llm runtime setup` / `llm config new` | Yes. |

Each layer mirrors the same shape — `runtimes/{id}/`, `configs/{id}.yaml`, `benchmarks/{id}/`. Discovery walks both. **The user layer wins on id collision.**

### 8.2 Behavior changes

- `llm list` shows a `source` column (`scaffold` / `user`). `llm runtime info <id>` and `llm config show <id>` print the source as part of their headers.
- `llm runtime setup --kind custom` writes to `$LLM_DATA_ROOT/user/runtimes/<id>/` instead of `repo_root/runtimes/<id>/`. Wizard UX otherwise unchanged.
- `llm config new` / `llm config setup` write to `$LLM_DATA_ROOT/user/configs/<id>.yaml`. Configs referencing scaffold runtimes is the normal case and Just Works.
- `llm runtime install <scaffold-id>` continues to read scripts from `$LLM_SCAFFOLD_DIR/runtimes/<id>/` and write the `.installed` marker into `$LLM_RUNTIMES/<id>/`. Unchanged from today.
- A user layer entry that shadows a scaffold id is flagged in `llm list` (e.g. ` (overrides scaffold)`). This is intentional friction — the user meant to override.

### 8.3 `repo_root` becomes dev-only

`repo_root` flips from required to optional in `KEY_REGISTRY` (`src/llm_cli/core/settings.py`). When set, it replaces the `scaffold` layer entirely so a contributor sees their checkout's edits live. When unset, normal users never know it exists.

A new accessor in `src/llm_cli/core/repo.py` (working name: `scaffold_root()`) returns the effective read source for shipped assets: `repo_root` if configured, else `$LLM_SCAFFOLD_DIR`. The existing `repo_root()` function gains a clear "raises if not configured" docstring for the few callers that genuinely need the dev override.

### 8.4 Drift footgun retired

In the v0.2.0 layout, `repo_root` is both the read source and the customization target. `git pull` can conflict with user customizations. The new layout makes the scaffold dir CLI-managed and treated as throwaway: `git fetch && git checkout <tag>` is always safe because nothing the user wrote lives there.

## 9. Section 3 — The `llm update` command

### 9.1 Default invocation

```
$ llm update
Checking for updates...
  CLI:      0.3.0  →  0.4.1   (PyPI)
  Scaffold: v0.3.0 →  v0.4.1   (github.com/mtopcu1/local-llm-scaffold)

Changelog highlights:
  • feat(runtimes): add tensorrt-llm preset
  • fix(serve): respect LLM_SERVE_HOST on systemd mode
  • ... (full changelog: https://github.com/.../releases/tag/v0.4.1)

Continue? [Y/n]
```

### 9.2 Steps, in order

1. **Detect.** Query PyPI's JSON API (`https://pypi.org/pypi/localllm-cli/json`, field `info.version`). Query the scaffold remote with `git ls-remote --tags --sort=v:refname` for the highest `v*` tag. Compare both to currently-installed values. Exit early with `Already up to date.` if both match.
2. **Show changelog.** Fetch the GitHub Release body for the new tag via `gh api repos/.../releases/tags/<tag>` if `gh` is available, else the unauthenticated GitHub REST API. Print a short summary + URL. Confirm interactively unless `--yes`.
3. **Service-running guard.** If `llm status` reports a service in any mode (`foreground` / `background` / `systemd`), refuse with: `"Stop the running service first (llm stop), or pass --restart to have update stop+start it."`
4. **Stage the wheel.** Run `pipx upgrade localllm-cli --pip-args='--upgrade-strategy=eager'`. If pipx is not present (e.g. editable dev install), fall back to `pip install --upgrade localllm-cli` in the same env, **unless** `repo_root` is set — in dev mode, refuse with "this is an editable install; `git pull` in your checkout instead."
5. **Stage the scaffold.** Record current tag, then in `$LLM_SCAFFOLD_DIR`: `git fetch --tags --depth=1 origin` and `git checkout v0.4.1`. Sparse-checkout config is preserved.
6. **Verify.** Re-exec `llm --version` (must match the new wheel version) and `llm doctor --quick` against the new scaffold. On failure, automatically roll back the scaffold to the recorded previous tag, leave the new wheel installed but warn the user, and print the one-liner to roll back the wheel (`pipx install 'localllm-cli==<prev>' --force`).
7. **Persist.** Write `$LLM_SCAFFOLD_DIR/.scaffold-version` containing the new tag (used for the passive drift check; avoids touching `.git/` on every CLI invocation). Print `Updated to 0.4.1.` plus a single-line "breaking change" hint if the release notes flag any.

### 9.3 Flags

| Flag | Purpose |
|---|---|
| `--yes` / `-y` | Skip interactive confirmation. For CI / scripts. |
| `--check` | Don't update — print available versions and exit non-zero if behind. |
| `--scaffold-only` | Skip the pipx step. Used by `install.sh` and as an escape hatch. |
| `--cli-only` | Skip the scaffold step. For dev-mode (`repo_root` set). |
| `--restart` | If a service is running, `llm stop` it, update, then re-`serve` the same config in the same mode. Off by default. |

Not shipped at v0.3.0 (deferred until concrete demand): `--pin <version>`, `--rollback`, `--channel <name>`, `--branch <name>`.

### 9.4 Passive drift detection (every invocation)

Every CLI invocation reads `$LLM_SCAFFOLD_DIR/.scaffold-version` (cheap) and compares it to `llm_cli.__version__`.

- **Patch-level mismatch** (e.g. CLI 0.4.1, scaffold v0.4.0): single-line yellow warning printed at most once per CLI invocation (not persisted), command proceeds.
- **Minor-or-major mismatch** (e.g. CLI 0.5.0, scaffold v0.4.1): destructive commands (`serve`, `runtime install`, `model pull`) **refuse** with "scaffold version drift — run `llm update --scaffold-only`". Non-destructive commands (`list`, `status`, `logs`, `--version`) warn but proceed.
- **Missing file** (very old install or manually deleted): warn and suggest `llm update --scaffold-only`. Same destructive-vs-non-destructive split as above.

### 9.5 What `update` is NOT

- Not a `pipx` wrapper (no `--include-deps` etc. leak through).
- Not a `git` wrapper (no `--branch`, `--commit`, etc.).
- Never touches `$LLM_DATA_ROOT/user/`. Hard rule.
- Never auto-updates installed runtimes or pulled model weights. Those stay explicit via `llm runtime rebuild` / `llm model pull --force`.

## 10. Section 4 — Versioning automation

### 10.1 Tool

[`release-please`](https://github.com/googleapis/release-please) GitHub Action, with the `python` release type. Picked over `semantic-release` because release-please uses a **long-lived release PR** as the human-merge gate — releases don't happen on every push to `main`. For a tool that runs shell scripts on people's machines, that gate is worth keeping.

### 10.2 Conventional Commits subset

| Prefix | Bump | Used for |
|---|---|---|
| `feat:` | minor | New CLI commands, wizard steps, runtime presets, flags. |
| `fix:` | patch | Bug fixes. |
| `feat!:` / `fix!:` / footer `BREAKING CHANGE:` | minor (pre-1.0 default) | Config schema breakage, removed commands, changed defaults. |
| `chore:` / `docs:` / `test:` / `refactor:` / `ci:` / `style:` | none | Excluded from CHANGELOG, no bump. |
| `perf:` | patch | Surfaces under "Performance" in CHANGELOG. |

Pre-1.0 quirk: under release-please defaults, `feat!:` bumps minor (0.x.y → 0.(x+1).0), not major. Acceptable for the current project phase. When the project hits 1.0 we revisit.

### 10.3 Files maintained automatically

- `pyproject.toml` — `version` field.
- `src/llm_cli/__init__.py` — `__version__ = "..."` with an `# x-release-please-version` marker comment.
- `CHANGELOG.md` — created and maintained by release-please.

### 10.4 Repo additions

- `release-please-config.json`:

  ```json
  {
    "release-type": "python",
    "packages": {
      ".": {
        "package-name": "localllm-cli",
        "extra-files": [
          { "type": "generic", "path": "src/llm_cli/__init__.py" }
        ]
      }
    },
    "changelog-sections": [
      { "type": "feat",  "section": "Features" },
      { "type": "fix",   "section": "Bug Fixes" },
      { "type": "perf",  "section": "Performance" },
      { "type": "docs",  "section": "Documentation", "hidden": false }
    ]
  }
  ```

- `.release-please-manifest.json`: initial state `{".": "0.2.0"}`.

### 10.5 GitHub Actions

Two workflows, both new:

1. **`.github/workflows/release-please.yml`** — runs on `push: main`. Opens/updates the release PR.
2. **`.github/workflows/publish.yml`** — runs on `release: published` (fired by release-please when its PR is merged). Steps: checkout the tag → `python -m build` → `twine upload --skip-existing` via PyPI **OIDC trusted publisher** (no `PYPI_API_TOKEN` secret). Also attaches the wheel + sdist to the GitHub Release.

### 10.6 Tag is the single source of truth

Because the scaffold lives in the same repo, the release tag (`v0.4.1`) **is** the scaffold checkout target for `llm update`. One number, two consumers. Zero drift risk between code and assets at release time.

### 10.7 Maintainer cadence

A maintainer's per-release flow becomes: write Conventional Commit messages → merge PRs into `main` → the release PR accumulates → when ready to release, review the release PR (version + CHANGELOG) → merge it → tag, GitHub Release, PyPI publish all happen automatically.

## 11. Section 5 — Branch / dev workflow (no published branch builds)

### 11.1 The dev install path

`scripts/install-dev.sh` (or a `make dev` target). The recipe:

```bash
git clone https://github.com/mtopcu1/local-llm-scaffold.git
cd local-llm-scaffold
pipx install --editable . --force --suffix=-dev
llm-dev settings edit repo_root "$(pwd)"
llm-dev setup
```

Three deliberate choices in there:

1. **`pipx install --editable`** — code changes in `src/` are picked up live.
2. **`--suffix=-dev`** — installs the binary as `llm-dev`, not `llm`. **Stable `llm` and dev `llm-dev` coexist on the same machine.** This is the single most important UX detail; without it, "try this PR" wrecks the user's working install.
3. **`repo_root` set to the checkout** — flips on the dev-mode override from §8. The scaffold layer becomes the live checkout instead of `$LLM_SCAFFOLD_DIR`. Manifest/script changes are picked up live too.

### 11.2 Contributor "try this PR" flow

`CONTRIBUTING.md` documents one recipe:

```bash
gh pr checkout 123
./scripts/install-dev.sh
llm-dev <whatever-you-want-to-test>
# when done:
pipx uninstall localllm-cli-dev
```

That is the complete story for testing unreleased code.

### 11.3 CI on branches (separate from release CI)

Two workflows on PRs/branches, both run on `ubuntu-latest`:

1. **`.github/workflows/ci.yml`** — runs on every PR and every `push: main`. Steps: `pip install -e '.[dev]'` → `pytest` → `llm doctor render-requirements && git diff --exit-code` (catches forgotten regenerations) → `llm specs --check` where feasible.
2. **`.github/workflows/build-check.yml`** — runs on PRs that touch `pyproject.toml` or `src/`. Steps: `python -m build` → `twine check dist/*`. Verifies the wheel would build cleanly.

PTY/WSL-only tests stay marked and skipped on Linux CI as they are today (pyproject's `pexpect>=4.9; sys_platform != 'win32'` and the `tui` pytest marker handle this).

### 11.4 What's explicitly NOT here

- No PyPI Test index usage.
- No per-PR ephemeral install URLs.
- No `--channel edge` knob inside `llm update`.
- No `--branch <name>` flag on `llm update`.

If demand for "try the unreleased fix" gets loud later, the cheapest add-on is per-branch wheels as GitHub Release assets. The wheel-installation step in `llm update` (§9 step 4) is factored so it can later accept a URL source. We don't build that scaffolding now.

## 12. Section 6 — Migration from v0.2.0

### 12.1 Existing v0.2.0 install topology

- Git clone at `$repo_root` (e.g. `~/local-llm-scaffold/`).
- Editable venv at `$LLM_DATA_ROOT/.cli-venv` (e.g. `~/llm/.cli-venv`).
- Symlink `~/.local/bin/llm → $LLM_DATA_ROOT/.cli-venv/bin/llm`.
- `~/.config/llm/config.yaml` with `data_root` + `repo_root` required.
- User-authored items potentially mixed into the cloned tree:
  - `repo_root/runtimes/<custom-id>/` from `llm runtime setup --kind custom`
  - `repo_root/configs/<user-id>.yaml` from `llm config new` / `config setup`
  - Possibly edits to shipped scripts (rare but possible)

### 12.2 The migration command

`scripts/migrate-from-v0.2.sh`, shipped in the v0.3.0 release. README's "Upgrading from 0.2.x" section is four lines:

```bash
cd ~/local-llm-scaffold
git fetch && git checkout v0.3.0
./scripts/migrate-from-v0.2.sh
# follow on-screen instructions
```

The script is **idempotent** and **dry-run by default**.

### 12.3 Pass 1 — `--plan` (default, no writes)

Prints a precise plan:

```
Migration plan for /home/melih/local-llm-scaffold → 0.3.0

Detected current layout:
  repo_root        : /home/melih/local-llm-scaffold    (v0.2.0 editable install)
  data_root        : /home/melih/llm
  LLM_SCAFFOLD_DIR : /home/melih/.local/share/localllm/scaffold  (will be created)
  LLM_USER_DIR     : /home/melih/llm/user                        (will be created)

User-authored items to be moved out of repo_root:
  runtimes/my-llamacpp-debug/    -> $LLM_DATA_ROOT/user/runtimes/my-llamacpp-debug/
  configs/llamacpp__qwen2-7b__debug.yaml -> $LLM_DATA_ROOT/user/configs/...

Shipped items with local modifications (need your call):
  runtimes/llamacpp/serve.sh     (modified vs v0.3.0)
    [k]eep modified copy as $LLM_DATA_ROOT/user/runtimes/llamacpp-local/serve.sh
    [d]iscard modifications
    [a]bort migration

CLI install changes:
  remove   ~/.local/bin/llm symlink
  remove   /home/melih/llm/.cli-venv  (after confirming pipx install works)
  install  pipx install localllm-cli==0.3.0

Settings changes:
  unset    repo_root  (was: /home/melih/local-llm-scaffold)
           (kept in /home/melih/.config/llm/config.yaml.bak)

Run with --apply to execute this plan.
```

### 12.4 Pass 2 — `--apply`

Executes in this order, with rollback on any failure:

1. Back up `~/.config/llm/config.yaml` → `~/.config/llm/config.yaml.bak`.
2. **Diff and copy user content.** Compare `repo_root/runtimes/` and `repo_root/configs/` against the v0.3.0 tag's contents. Items present in `repo_root` but not in the tag are user content → copy to `$LLM_DATA_ROOT/user/{runtimes,configs}/`. Items in both with different content trigger the interactive `[k]/[d]/[a]` prompt (or are decided up front by `--on-conflict={keep,discard,abort}` for non-interactive runs).
3. **Bootstrap pipx if missing.** Same logic as the fresh installer.
4. **Install the wheel.** Remove the v0.2.0 `~/.local/bin/llm` symlink first (otherwise pipx refuses over a name collision), then `pipx install 'localllm-cli==0.3.0'`. If pipx install fails here, abort *before* touching anything else — config, venv, symlink can all be restored.
5. **Initialize the scaffold dir.** Run the newly-installed `llm update --scaffold-only --yes`.
6. **Smoke test.** `llm --version` (expect `llm 0.3.0`), `llm list`, `llm doctor --quick`. On any failure: restore the symlink to the old venv, restore `config.yaml.bak`, leave the pipx install in place (harmless), print recovery instructions.
7. **Remove `repo_root` from settings.** Write updated `config.yaml`. Backup is preserved.
8. **Print closing instructions** — do not auto-delete the old clone or the old venv. Tell the user the clone is no longer needed and the venv (`$LLM_DATA_ROOT/.cli-venv`) can be removed at their discretion.

### 12.5 Code changes implied by the migration

- `src/llm_cli/core/settings.py`: `repo_root` flips `required: True` → `required: False` in `KEY_REGISTRY`.
- `src/llm_cli/core/repo.py`: add `scaffold_root()` accessor (returns `repo_root` if set, else `$LLM_SCAFFOLD_DIR`). Existing `repo_root()` keeps current behavior but docstring clarifies it's dev-only.
- All call sites that read `runtimes/`, `configs/`, `benchmarks/` switch to using a new `assets.iter_runtimes()` / `assets.iter_configs()` / etc. helpers that walk both layers (scaffold + user). This is a refactor across multiple `core/` and `commands/` modules — sequenced as part of the §2 implementation, not the migration script itself.
- `tests/unit/test_settings.py`: update `MissingSettingError` expectations for `repo_root`.

### 12.6 Docs sweep

- `README.md`: rewrite "Getting started" to pipx-first, with the old git-clone path linked from a "for developers" section.
- `docs/wsl-setup.md`: update to pipx path.
- `docs/repo-conventions.md`: rewrite "Settings vs configs" to introduce the scaffold/user layer split.
- `docs/add-a-runtime.md`, `docs/add-a-model.md`, `docs/add-a-config.md`, `docs/add-a-benchmark.md`, `docs/add-a-recommendation.md`: clarify where user authoring lands vs. where scaffold contributions live.
- `CONTRIBUTING.md` (new): the dev install path.

### 12.7 Lifecycle of the migration code

The migration script ships in v0.3.0 only. **Removed in v0.4.0.** Anyone still on 0.2.x at 0.4.0 release time can either chain via 0.3.x or do a fresh install. Maintaining migration code indefinitely is a tax pre-1.0 doesn't owe itself.

## 13. Release sequencing

Concrete cut order from current state to v0.3.0 released:

1. **In v0.2.x land:** implement release-please + `ci.yml` + `publish.yml` first — no behavior change, just plumbing. Cut a `v0.2.1` patch release as a smoke test of the publish pipeline. PyPI gains `localllm-cli==0.2.1` even though no user is told to use it yet.
2. **In a feature branch:** implement the layered asset model (§2), `llm update` command (§3), `migrate-from-v0.2.sh` (§6), and the docs sweep. This is the chunky PR.
3. **Cut `v0.3.0`** as the first user-facing distributed release. README updates to the pipx-first story. Old root `install.sh` becomes `scripts/install-dev.sh`.

Step 1 is a deliberately small first slice so the publish pipeline gets exercised before we lean on it for a real release.

## 14. Open questions for review

None blocking. A few items worth confirming during plan-writing:

- **PyPI package name** is currently `localllm-cli` (from `pyproject.toml`). Confirm it's available on PyPI before scheduling step 1 of §13; reserve the name if so.
- **GitHub Releases trusted publisher.** PyPI trusted-publisher setup is a one-time UI action on PyPI's web console; the implementation plan should call that out as a manual prerequisite.
- **`$LLM_SCAFFOLD_DIR` env var name and default path** (`~/.local/share/localllm/scaffold/`) — should this match XDG_DATA_HOME if set? Current choice is "honor `$XDG_DATA_HOME` like the settings file already honors `$XDG_CONFIG_HOME`." Spell out in implementation plan.
- **`llm doctor --quick`** referenced in §9.2 and §12.4 doesn't exist yet; either add it as part of the §9 implementation slice or use the existing `llm doctor` and accept slower update verification.
