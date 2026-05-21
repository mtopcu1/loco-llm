# LocalLLM Scaffold — Full Project Review

**Date:** 2026-05-18  
**Version reviewed:** 0.2.0 (`localllm-cli`)  
**Scope:** Security, code quality, UX, features, ship readiness  
**Method:** Static codebase audit, test inventory, docs/CLI flow review (no live penetration test)

---

## Executive summary

LocalLLM is a **well-architected personal control plane** for WSL2 local LLM serving: git-friendly configs, manifest-driven runtimes, typed params, lifecycle/systemd, and a differentiated wizard + advisor stack. For a **single-user lab tool**, it is close to shippable as v0.2. For **production or multi-user/shared-repo** use, several input-validation and shell-surface issues need fixing first.

| Area | Rating (1–10) | One-line verdict |
|------|---------------|------------------|
| **Security** | 6/10 | Good subprocess/YAML hygiene; ID validation and shell surfaces are the gap |
| **Code quality** | 8/10 | Clear structure, strong params/registry tests; TUI and some commands undertested |
| **Test confidence** | 7/10 | ~441 tests, strong integration coverage; no coverage metrics, TUI gaps |
| **UX** | 7/10 | Power users love wizards; steeper than Ollama for newcomers |
| **Feature completeness** | 6/10 | Core loop works; benchmarks/history/run shortcuts promised or implied but missing |
| **Maintainability** | 8/10 | Good `core/` vs `commands/` split; param grid TUI still monolithic |
| **Overall** | **7.2/10** | **Ship v0.2 as “personal preview” soon; harden before “production” label** |

### Ship soon?

**Yes, with caveats:**

- **Ship as 0.2 personal preview / lab tool** — core flows (setup → runtime → model → config → serve) are implemented, tested, and documented. Recent param grid UX is a real differentiator.
- **Do not label “production-ready”** until slug validation, systemd unit safety, and `extra_args` shell splitting are addressed (estimated 1–3 focused days).
- **Do not market “benchmark them”** until `loco bench` exists — README/tagline ahead of CLI.

---

## 1. Security

### Trust model (important context)

This tool assumes:

- **Single trusted user** on their own machine
- **Repo YAML and shell scripts are trusted** (you author or review them)
- **WSL2 Ubuntu** as primary runtime environment

Findings below distinguish **“fix before any shared/production use”** vs **“acceptable for solo dev, note for later.”**

---

### 1.1 Immediate attention (fix before production / shared configs)

| ID | Severity | Issue | Location | Impact |
|----|----------|-------|----------|--------|
| S-1 | **Critical** | `config_id` embedded in systemd unit via `.format()` without validation | `src/llm_cli/core/systemd_unit.py` | Newlines/special chars in config id could inject extra systemd directives → persistent user-level code execution on `loco serve --systemd` |
| S-2 | **Critical** | Custom runtime `serve.sh` runs user-authored shell (`bash -c "$INVOCATION_LINE"`) | `src/llm_cli/commands/runtime_cmd.py` | By design for BYO runtimes; dangerous if runtimes/configs come from untrusted sources |
| S-3 | **High** | Config/runtime/model IDs used in path joins without slug validation | `config_cmd.py`, `model_cmd.py`, `install_record.py` | `../` or slashes in ids could write/read outside `configs/`, `models/`, `runtimes/` |
| S-4 | **High** | Serve script path built as `runtimes/{runtime_id}/serve.sh` instead of resolved manifest path | `src/llm_cli/commands/serve.py` | Crafted runtime id in config could exec scripts outside repo |
| S-5 | **High** | `running.json` `log_path` not confined to `state/logs/` | `lifecycle_cmds.py`, `lifecycle.py` | Tampered state file → `loco logs` reads arbitrary files |
| S-6 | **High** | `extra_args` expanded unquoted in serve scripts | `runtimes/llamacpp/serve.sh`, `runtimes/vllm/serve.sh` | YAML config author can inject shell metacharacters at serve time |

**Actionable steps (priority order):**

1. **Add `validate_slug(id: str)`** — regex e.g. `^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$`; reject `/`, `\`, `..`, whitespace, newlines. Apply to `config_id`, `runtime_id`, `model_id` at CLI entry and wizard save.
2. **Systemd unit:** stop using `.format(config_id=…)`; use `systemd-escape` semantics or hard slug check before write.
3. **Serve paths:** resolve `serve.sh` from `RuntimeRecord.path` (discovered directory), not string concat with config’s runtime field alone.
4. **`loco logs`:** after `resolve()`, require `log_file.is_relative_to(repo / "state" / "logs")`.
5. **`extra_args`:** pass via env array or append to `"${ARGS[@]}"` without unquoted word-split (or document as trusted-author-only and block in validated configs).

---

### 1.2 Too insecure for a “production release” (even if acceptable for solo lab)

| ID | Severity | Issue | Notes |
|----|----------|-------|-------|
| S-7 | High | Full `os.environ.copy()` inherited by serve subprocesses | Secrets in parent env leak to child bash/HF processes |
| S-8 | High | Arbitrary `env:` names from `params.yaml` (`LD_PRELOAD`, etc.) | Allowlist `LLM_*` prefix for official runtimes |
| S-9 | High | `LLM_BUILD_EXTRA_PIP_PACKAGES` shell-split in vllm `build.sh` | Arbitrary pip/shell during install |
| S-10 | Medium | `loco doctor` runs `requires.verify.cmd` from repo YAML | Trusted repo assumption; risky on cloned untrusted repos |
| S-11 | Medium | vLLM `trust_remote_code` param exposed | Dangerous combined with non-loopback bind |
| S-12 | Medium | No enforcement of `127.0.0.1` bind; API keys optional | Misconfiguration exposes unauthenticated inference API |

**Actionable steps:**

6. **Env hygiene:** default serve env to explicit allowlist; opt-in `--inherit-env` for power users.
7. **Bind warnings:** `loco serve` warns if host ≠ loopback and no API key set.
8. **Custom runtime gate:** `loco runtime setup` / serve prints explicit trust warning; optional `--official-only` mode for paranoid installs.
9. **Remove unused `httpx` dependency** or use it — reduces supply-chain surface (`pyproject.toml`).

---

### 1.3 Minor / low importance (document or backlog)

| ID | Issue | Action |
|----|-------|--------|
| S-14 | `requirements.yaml` suggests `curl … \| bash` for HF CLI | Add note in docs; prefer packaged install |
| S-15 | `model add` symlinks arbitrary paths | Document symlink implications |
| S-16 | `EDITOR` env in runtime wizard | Local-user threat only |
| S-17 | World-executable bits on authored scripts | Minor hardening on multi-user systems |
| S-18 | No path containment assert after `.resolve()` in several modules | Defense-in-depth helper `assert_under(root, path)` |

---

### 1.4 Security positives (keep doing this)

- No `shell=True` / `os.system` in Python source
- Consistent `yaml.safe_load` (no unsafe loaders)
- HF URL host allowlist
- Typed param validation with unknown-key rejection
- Atomic writes for configs, registry, running state
- `HF_TOKEN` from environment only, not persisted in repo
- User systemd only (`systemctl --user`), no root escalation in CLI
- `shlex.quote` used in WSL/bash spawn paths

---

## 2. Code quality

### 2.1 Overall assessment

**Good.** The codebase reads like intentional engineering, not a spike:

- Clear **`core/` vs `commands/`** separation
- **Dataclasses + typed params** (`ParamSpec`, `ParamType`, validation errors)
- **Registry as hub** for discovery/validation
- **Lazy imports** to break cycles (`wizards.edit_params`, `chain` → commands)
- **Recent param grid decomposition** (`param_grid_build`, `_layout`, `_plain`, `_theme`, `wizard_shell`) — right direction

**Smells to watch:**

- `param_grid.py` ~650 lines with nested closures — hardest module to maintain
- `wizards` uses `list[Any]` for specs — weak typing at UI boundary
- No **ruff/mypy/pytest-cov** in CI — regressions rely on discipline

---

### 2.2 Tests — enough?

| Metric | Value |
|--------|-------|
| Tests collected | **441** |
| Unit test modules | ~34 |
| Integration test modules | ~17 |
| Source modules | ~40 |

**Well covered:**

- `params.py` (~32 unit tests)
- `registry.py` config/manifest validation (~23)
- `lifecycle.py` (~18+)
- CLI flows via `CliRunner` integration tests
- HF client/URL, settings, doctor, serve spawn, model registry
- Param grid: plain fallback, build, layout, theme (strong)

**Gaps:**

| Gap | Risk |
|-----|------|
| `_run_param_grid_tui` (interactive prompt_toolkit) | UX regressions (Keys.Any, footer, phases) — only smoke build test |
| `edit_params` end-to-end | Always stubbed in integration tests |
| `list_cmd` / `discover_benchmarks` | No dedicated tests |
| `get_config`, `validate_runtime_layout` | Used in production paths, lightly tested |
| `chain.py` real command wiring | Heavily mocked |
| No coverage % gate | Unknown blind spots |

**Bug-proof enough?**

- **For typed paths and CLI contracts:** largely yes — integration tests catch many footguns.
- **For TUI and edge-case validation:** moderate — manual testing still matters.
- **For security paths (slug traversal):** **no** — untested because validation doesn’t exist yet.

**Actionable steps:**

10. Add **`pytest-cov`** with threshold on `core/params`, `registry`, `lifecycle` (e.g. 85%+).
11. Add **`test_cli_list.py`** (list, `--json`, invalid filter, benchmarks row).
12. Add **2–3 characterization tests** for param grid TUI (meta → list → save, abort, detail validation error).
13. Add unit tests for **`validate_slug`** once implemented (security + regression).
14. Consider **`mypy` on `core/`** in CI (optional, incremental).
15. Extract **`_run_param_grid_tui`** render/focus into testable pure functions (already started with `wizard_shell`, `param_grid_layout`).

---

### 2.3 Maintainability / understandability

| Strength | Example |
|----------|---------|
| Docs match code | `docs/wizards.md`, `docs/lifecycle.md`, superpowers specs |
| Single responsibility emerging | param grid split across 6 files |
| Test isolation | `conftest.py` XDG_CONFIG_HOME autouse |
| Explicit error lists | registry validation vs exceptions |

| Weakness | Recommendation |
|----------|----------------|
| Long config/runtime command files | Extract validation helpers to `core/` |
| Benchmark discovery without bench CLI | Either implement or hide from `loco list` until ready |
| Duplicate Windows path listings in git | Harmless noise |

**Verdict:** A new contributor can follow **setup → serve** in a day; param grid/TUI needs half a day extra. **Maintainability: 8/10.**

---

## 3. UX

### 3.1 Intuitiveness

**Strengths:**

- **`loco setup` chain** — sensible Y/n defaults, duplicate-model menu, history logging
- **Param grid (0.2)** — list/detail, meta step, advisor hints in detail, plain fallback for CI
- **`loco advisor` → config setup** — closes “what should ctx be?” loop
- **`loco doctor`** — prerequisites + systemd linger advisory
- **Stub runtime** — fast smoke without weights

**Friction (vs Ollama / LM Studio):**

| Friction | Why it hurts |
|----------|--------------|
| WSL + repo cwd required | Easy to run from wrong shell/directory |
| Runtime → model → config layers | Steep mental model for newcomers |
| Long config ids | `llamacpp__model__default` vs `qwen2.5:7b` |
| `--help` doesn’t teach the journey | Wizards table buried in docs |
| No `loco serve` default | Always need full config id |
| Post-serve output minimal | No base URL / sample curl |
| Benchmarks listed but not runnable | Feels incomplete |
| Advisor narrow (llamacpp ctx/layers) | vLLM users see empty recommendations |

**UX rating: 7/10** — excellent for reproducibility-focused users; not yet “install and chat in 60 seconds.”

---

### 3.2 Improvement areas (actionable)

| # | Improvement | Effort | Impact |
|---|-------------|--------|--------|
| U-1 | **`loco quickstart`** or richer root `--help` | Small | High for onboarding |
| U-2 | **Post-serve ready card** (base URL, curl, model name) | Small | High |
| U-3 | **`loco status` shows** host, port, model, runtime, URL | Small | High |
| U-4 | **First-run param grid hint** (3 lines: Enter, Ctrl+S, Esc) | Tiny | Medium |
| U-5 | **Early cwd/WSL detection** with actionable errors | Medium | High |
| U-6 | **Rename/clarify `setup --default`** (“settings only, no chain”) | Tiny | Medium |
| U-7 | **`loco config edit <id>`** reusing param grid | Medium | High |
| U-8 | **Skip HF URL prompt** when stub runtime chosen in chain | Tiny | Low |

---

## 4. Features — “bomb” ideas

Prioritized by **fit with existing code** × **user wow**.

### Tier A — Ship next (mostly wiring)

| Feature | Why it’s a bomb | Already in repo |
|---------|-----------------|-----------------|
| **`loco bench` + `loco results`** | Fulfills README promise; reproducible quant comparisons | `benchmarks/`, `discover_benchmarks`, stub-bench, design specs |
| **`loco history`** | Timeline of setup/advisor/serve/debug | `state/history.jsonl`, `append_history` everywhere |
| **`loco config edit <id>`** | Re-open grid on existing YAML | `edit_params`, `validate_params`, atomic write |
| **Post-serve ready card** | Instant “it works” moment | host/port in config, healthcheck patterns |
| **Expand advisor (vLLM, fit check)** | “Will this model fit?” before 20GB download | `detect_all`, model sizes, `recommendations.py` extensibility |

### Tier B — Strong differentiation

| Feature | Why it’s a bomb |
|---------|-----------------|
| **`loco run <model-id>`** | Ollama-shaped shortcut: auto config + serve if one compatible runtime |
| **`loco model search` / HF picker** | `hf_client` metadata + pull pipeline exists |
| **`loco default <config-id>`** | `loco serve` with no args — preference file, not second daemon |
| **Drift-aware doctor → one-key rebuild** | `install_record` schema hash + `runtime rebuild` |
| **Bench-driven advisor loop** | Bench results feed param suggestions — unique tuning story |

### Tier C — Bigger bets

- **`loco chat`** thin REPL over OpenAI-compatible endpoint
- **TUI dashboard** (`list` + `status` + `history` + grid)
- **Config preset library** (`configs/presets/`, `--preset throughput`)

**Feature strategy:** Lean into **“reproducible, machine-aware local lab”** — not cloning Ollama simplicity wholesale.

---

## 5. Consolidated action plan

Review this list later; items grouped by theme.

### P0 — Before calling it “production” (security)

- [ ] **S-1–S-6:** Slug validation, systemd safe embedding, path containment, extra_args fix

### P1 — Before public v0.2 announcement (UX + promise)

- [ ] **U-2, U-3:** Post-serve ready card + richer status
- [ ] **U-1:** Quickstart in help
- [ ] **Feature:** `loco history` (read `history.jsonl`)
- [ ] **Feature or hide:** benchmarks in `loco list` until `loco bench` ships

### P2 — Quality & confidence (1 week)

- [ ] **Tests 10–13:** cov gate, list_cmd, TUI characterization, slug tests
- [ ] **S-7–S-9:** env allowlist, bind warnings, pip install hardening
- [ ] **U-7:** `loco config edit`

### P3 — Differentiation (next milestone)

- [ ] **`loco bench` / `loco results`**
- [ ] **`loco run <model>`**
- [ ] **Advisor vLLM + serve-fit check**
- [ ] **HF model picker wizard**

---

## 6. Ratings summary

| Category | Score | Notes |
|----------|-------|-------|
| Security (solo lab) | **7/10** | Acceptable with trusted repo; fix slugs before sharing |
| Security (production) | **4/10** | Systemd injection + path traversal blockers |
| Code quality | **8/10** | Clean architecture, typed core |
| Test suite | **7/10** | 441 tests; uneven TUI/security coverage |
| Bug resistance | **7/10** | Strong validation layer; TUI/security edges remain |
| Maintainability | **8/10** | Good docs and module split |
| UX (power user) | **8/10** | Wizards, advisor, systemd story |
| UX (newcomer) | **6/10** | WSL + 3-layer model |
| Feature vs promise | **6/10** | Bench/history/run gaps |
| **Overall** | **7.2/10** | Strong 0.2 preview; not production-hardened |

---

## 7. Ship readiness assessment

### Can you ship soon?

| Audience | Recommendation |
|----------|----------------|
| **You (solo, WSL lab)** | **Yes — ship 0.2 now.** Tag release, use personally, iterate. |
| **Friends / small team (shared git repo)** | **After P0 security** (slug + systemd + paths). ~1–3 days. |
| **“Production” / internet-exposed** | **Not yet.** Need P0 + bind/auth defaults + env hardening. |
| **Open-source “1.0” marketing** | **After P1 + bench CLI** so README claims match reality. |

### Suggested release framing

> **v0.2.0 — Personal preview.** Reproducible local LLM configs, wizards, llamacpp/vloco runtimes, systemd serve. Single-user WSL2 lab tool. Not hardened for untrusted input or network exposure.

### What you’ve nailed

- Git-native configs and manifests
- Typed param pipeline end-to-end
- Lifecycle (bg/systemd/switch/logs) with reconciliation
- 0.2 wizards + param grid (recent UX is genuinely good — “like butter” tier for a CLI)
- Test discipline far above average for a solo scaffold

### What would move the needle most

1. **Slug validation everywhere** (security + peace of mind)
2. **`loco bench` + `loco history`** (promise + debuggability)
3. **Post-serve ready card** (first-run delight)
4. **pytest-cov + 3 TUI tests** (confidence to keep iterating UX)

---

## Appendix A — Files reviewed (representative)

- `src/llm_cli/commands/` — config, serve, runtime, model, setup, lifecycle, advisor
- `src/llm_cli/core/` — params, registry, lifecycle, chain, wizards, param_grid*, wizard_shell, systemd_unit, serve_spawn
- `runtimes/llamacpp/`, `runtimes/vllm/` — serve.sh, params.yaml, build.sh
- `tests/` — unit + integration inventory
- `docs/wizards.md`, `README.md`, superpowers specs

## Appendix B — Review limitations

- No dynamic exploitation or fuzzing performed
- WSL runtime not exercised live in this review pass
- GPU/VRAM advisor accuracy not benchmarked against real hardware
- User-specific `configs/` and `state/` not inspected

---

*Generated for later review. Revisit action plan sections P0–P3 and update checkboxes as items land.*
