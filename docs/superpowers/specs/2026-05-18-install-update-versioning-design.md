# Install, Update & Versioning

_Date: 2026-05-18_
_Status: Draft — pending user review_

## 1. Purpose

Give **public users** a way to install and update LocalLLM **without git**: curl-style install, semver releases, and `llm update`. Official runtime manifests ship in a **read-only bundle**; user-owned data (configs, models, builds, state) lives under `~/llm`.

Contributors keep the existing **dev install** (git clone + editable `pip install -e`).

## 2. Decisions (from brainstorming)

| Question | Choice |
|----------|--------|
| Primary audience | **Public users** who never touch git |
| Install model | **Read-only bundle** — official runtimes only in the install; custom runtimes/configs in user data dirs |
| Distribution | **Approach 1** — release tarball + install script + `llm update` (not PyPI-only, not hidden git clone) |

## 3. Goals

- One-liner install: `curl -fsSL https://…/install.sh | bash`
- Idempotent upgrade: `llm update` (or `llm update --check`)
- Semver releases tagged on `main`; dev builds derive version from git
- Atomic upgrades via versioned release dirs + `current` symlink
- Clear split: **bundle** (read-only, vendor-owned) vs **data_root** (user-owned)
- Dev path unchanged for contributors working in a git clone

## 4. Non-goals (v1)

- Standalone binary (PyInstaller/Nuitka)
- PyPI as primary distribution channel
- Auto-update on every CLI invocation (optional notify-only later)
- Custom runtime authoring in bundle mode (`llm runtime setup` custom branch disabled; message points to dev install)
- Per-PR version bumps or branch-name semver for public releases
- Windows-native install (WSL2/Linux only, same as today)
- Downgrade UX beyond keeping the previous release directory on disk

## 5. On-disk layout

### 5.1 Public (bundle) install

```
~/.local/share/localllm/
  venv/                         # CLI virtualenv (shared across releases)
  releases/
    0.2.0/
      VERSION                   # plain text: 0.2.0
      SHA256SUMS                # checksums for manifest verification
      manifest.json             # file list + metadata
      wheel/
        localllm_cli-0.2.0-py3-none-any.whl
      bundle/
        runtimes/               # official manifests + scripts (read-only)
        benchmarks/             # read-only wrappers
        templates/
          configs/              # example configs copied on first setup, not loaded live
  current -> releases/0.2.1/    # symlink to active release

~/.local/bin/llm                # symlink -> ~/.local/share/localllm/venv/bin/llm

~/llm/                          # data_root (user-writable)
  configs/                      # user launch configs (NEW default location)
  runtimes/                     # built runtime artifacts (.installed, builds)
  models/
  cache/
  state/
```

### 5.2 Settings file (`~/.config/llm/config.yaml`)

```yaml
data_root: ~/llm
install_root: ~/.local/share/localllm/current/bundle
configs_dir: ~/llm/configs
install:
  kind: bundle                  # bundle | source
  venv: ~/.local/share/localllm/venv
  channel: stable
  version: "0.2.1"
  releases_dir: ~/.local/share/localllm/releases
```

**Dev install** keeps today’s shape:

```yaml
data_root: ~/llm
repo_root: /path/to/local-llm-scaffold
install:
  kind: source
  venv: ~/llm/.cli-venv
```

### 5.3 Resolution rules

| Resource | Bundle mode | Source (dev) mode |
|----------|-------------|-------------------|
| Official runtime manifests | `{install_root}/runtimes/` | `{repo_root}/runtimes/` |
| User launch configs | `{configs_dir}/*.yaml` | `{repo_root}/configs/*.yaml` |
| Runtime build output | `{runtimes_dir}` (under data_root) | same |
| Bash script cwd / `LLM_REPO_ROOT` | `install_root` (bundle root) | `repo_root` |

Introduce `bundle_root()` / extend `Settings` with `install_kind`, `install_root`, `configs_dir`. Repo-aware commands resolve paths via a single helper (`scaffold_root()`, `configs_root()`) instead of hard-coding `repo_root()`.

## 6. Versioning

### 6.1 Release versions (public)

- **SemVer** on git tags: `v0.2.0`, `v0.2.1`, `v0.3.0`
- Tagging is **manual/intentional** when shipping — not on every merge to `main`
- Release notes on GitHub Releases

### 6.2 Dev versions (contributors)

- Use **hatch-vcs** (or setuptools-scm): version derived from nearest tag
- Example: `0.3.0.dev5+g1a2b3c4d` on commits after `v0.2.0`
- Dirty tree may append local suffix (tool default)

### 6.3 Single source of truth

- Remove duplicate `__version__` string; read installed version via `importlib.metadata.version("localllm-cli")`
- `pyproject.toml`: `dynamic = ["version"]` + hatch-vcs config
- `llm --version` and `llm update --check` use package metadata

### 6.4 Branch / preview builds (contributors only, not v1 public)

- `pip install -e "git+https://github.com/mtopcu1/local-llm-scaffold@branch#egg=localllm-cli"` for internal testing
- Optional later: CI uploads wheel artifacts on `main` nightly — not required for v1

## 7. Release pipeline (CI)

Trigger: **git tag push** matching `v*`.

Steps:

1. Run test suite (`pytest`, optionally `pytest -m tui` on Linux)
2. Build wheel with hatch (`localllm_cli-{version}-py3-none-any.whl`)
3. Assemble bundle tree: copy `runtimes/`, `benchmarks/`, `templates/configs/` from repo
4. Write `VERSION`, `manifest.json`, `SHA256SUMS`
5. Create `localllm-{version}.tar.gz`
6. Publish GitHub Release with assets:
   - `localllm-{version}.tar.gz`
   - `localllm_cli-{version}-py3-none-any.whl` (optional standalone)
7. Update **`stable.json`** manifest (see §8) on the release or default branch

`manifest.json` (inside tarball):

```json
{
  "version": "0.2.1",
  "min_python": "3.11",
  "files": {
    "wheel": "wheel/localllm_cli-0.2.1-py3-none-any.whl",
    "bundle/runtimes": "…"
  }
}
```

## 8. Update manifest

**v1 source of truth:** `releases/stable.json` on the default branch, updated by the release CI job when a tag is published (commit back to `main` or store only as a release asset — pick one in implementation; default: **committed file** so install works without GitHub API tokens).

URL: `https://raw.githubusercontent.com/mtopcu1/local-llm-scaffold/main/releases/stable.json`

```json
{
  "channel": "stable",
  "version": "0.2.1",
  "tarball_url": "https://github.com/mtopcu1/local-llm-scaffold/releases/download/v0.2.1/localllm-0.2.1.tar.gz",
  "sha256": "<hex>",
  "published_at": "2026-05-18T12:00:00Z",
  "min_python": "3.11"
}
```

Install script and `llm update` fetch this file first, then download the tarball from `tarball_url`.

## 9. Install script (`scripts/install.sh`)

Public entrypoint (also served via GitHub raw / release asset):

```bash
curl -fsSL https://github.com/mtopcu1/local-llm-scaffold/releases/latest/download/install.sh | bash
```

Behavior:

1. Require Linux/WSL, Python ≥ 3.11
2. Resolve version: `$LOCALLLM_VERSION` env, else fetch `stable.json`
3. Download `localllm-{version}.tar.gz` to temp dir; verify `sha256`
4. Extract to `$RELEASES_DIR/{version}/`
5. Create venv at `~/.local/share/localllm/venv` if missing
6. `pip install --upgrade pip` + `pip install` wheel (non-editable, `--force-reinstall` on upgrade)
7. Atomically point `current` symlink at new release dir
8. Write/update `~/.config/llm/config.yaml` (preserve existing `data_root` overrides)
9. Create `~/llm/configs/` if missing; copy template configs if dir empty
10. Symlink `~/.local/bin/llm`
11. Run `llm setup --default` if first install (skip interactive chain unless `$LOCALLLM_SETUP=1`)

Existing repo-root `install.sh` becomes **`scripts/install-dev.sh`** (editable install from clone) or keeps name with a banner when run from git checkout.

Environment variables:

| Var | Purpose |
|-----|---------|
| `LOCALLLM_VERSION` | Pin install to specific semver |
| `LOCALLLM_CHANNEL` | Default `stable` |
| `LOCALLLM_INSTALL_DIR` | Override `~/.local/share/localllm` |
| `LOCALLLM_SKIP_SETUP` | Skip post-install setup (same as today) |

## 10. `llm update` command

```
llm update [--check] [--version VERSION] [--channel stable]
```

| Flag | Behavior |
|------|----------|
| (default) | Fetch manifest, compare, download, install if newer |
| `--check` | Print current vs latest; exit 0 if up to date, 1 if upgrade available |
| `--version` | Pin target version instead of latest stable |

Flow:

1. Refuse in **source/dev** mode with hint: `git pull && pip install -e .` (or add `llm update --dev` later)
2. Load `install.version` from settings
3. Fetch `stable.json`; compare semver
4. If up to date → print message, exit 0
5. Download tarball → verify sha256 → extract to `releases/{version}/`
6. `pip install --force-reinstall` wheel into configured venv
7. Repoint `current` symlink; update `install.version` in settings
8. Print summary + suggest `llm doctor`

**Rollback (manual v1):** previous release dir remains under `releases/`; user can repoint `current` symlink or re-run `llm update --version PREVIOUS`.

## 11. Code changes (summary)

| Area | Change |
|------|--------|
| `settings.py` | Add `install_kind`, `install_root`, `configs_dir`, nested `install.*`; resolution helpers |
| `repo.py` | Generalize to `scaffold_root()` + `configs_root()` |
| `config_cmd.py` | Read/write configs under `configs_dir` in bundle mode |
| `registry.py` | Load manifests from `scaffold_root()/runtimes` |
| `runtime_cmd.py` | Disable custom runtime wizard when `install_kind == bundle` |
| `setup.py` | Branch on install kind; seed configs dir from templates |
| `main.py` | Add `update` command group |
| `commands/update.py` | New: check/download/install logic |
| `pyproject.toml` | hatch-vcs dynamic version |
| `install.sh` | Split dev vs public scripts |

## 12. Error handling

| Failure | Behavior |
|---------|----------|
| Network / 404 | Clear error; exit 1; leave current install untouched |
| Checksum mismatch | Delete partial extract; exit 1; do not repoint `current` |
| Python too old | Fail before download with required version |
| Disk full mid-extract | Fail; partial dir removed; `current` unchanged |
| `llm update` in source mode | Exit 1 with dev instructions |
| Missing `install` section in settings | Treat as legacy source install if `repo_root` set; else prompt re-run install script |

## 13. Testing

| Layer | Coverage |
|-------|----------|
| Unit | Semver compare; settings resolution for bundle vs source; `configs_root()` paths |
| Unit | Update logic with mocked HTTP + fixture tarball |
| Integration | Config write/read under temp `configs_dir` |
| Integration | Registry loads from bundle layout fixture |
| CI | On tag: build tarball, smoke `install.sh` against fixture in ephemeral container |
| Manual | WSL curl install → `llm update --check` → upgrade across two tagged releases |

## 14. Migration & compatibility

- **Existing dev users:** no change if `install.kind` absent and `repo_root` present → source mode
- **Existing `repo_root/configs/`:** dev mode only; bundle installs start fresh under `~/llm/configs/`
- **Committed `configs/*.yaml` in git:** remain dev fixtures/examples; also copied into release `templates/configs/`

## 15. Documentation updates

- `README.md`: public install one-liner + `llm update`
- `docs/wizards.md` or new `docs/install.md`: dev vs bundle, directory layout, rollback
- Contributor note: releases require tagging + CI

## 16. Implementation phases

**Phase 1 — Foundation**

- hatch-vcs versioning; `Settings` + path helpers; `configs_dir` plumbing
- Bundle vs source detection

**Phase 2 — Release artifacts**

- CI workflow; tarball assembly; `stable.json`; public `install.sh`

**Phase 3 — Update command**

- `llm update` / `--check`; wire to manifest + pip reinstall

**Phase 4 — Polish**

- Disable custom runtime in bundle mode; template config seeding; docs

---

## Appendix: comparison to other CLIs

| Tool | Model | LocalLLM v1 equivalent |
|------|-------|------------------------|
| Ollama | Single binary + curl install script | Tarball bundle + venv wheel |
| OpenCode | Multi-channel binary + `opencode upgrade` | `stable.json` + `llm update` |
| pipx tools | PyPI wheel | We also ship non-Python bundle assets (runtimes) |

LocalLLM differs because **runtime manifests are part of the product**, not just the Python package — hence tarball bundle rather than PyPI-only.
