# Dashboard workflow report: full runtime → model → config → serve

**Date:** 2026-05-21  
**Tester:** Cursor agent (`dashboard-workflow-test` skill)  
**Environment:** WSL, dashboard http://127.0.0.1:7878, loco v1.4.0 (update badge v1.5.0), branch `feat/ux-improvements` (dashboard dist may not include latest SPA/job fixes)

## Summary

The workflow was **partially completed**. Runtimes were cleared (already uninstalled), **llamacpp** installed successfully via the dashboard, **vllm** failed from the dashboard (Python 3.14 / pinned `v0.8.5`) but succeeded via CLI with `vllm_version=0.21.0`. Small **GGUF** and **safetensors** models pulled successfully. Three new configs were created. **Serve/switch** works after setting `repo_root` in settings; without it, serve crashes. Several **UX and lifecycle bugs** were found, including orphan `hf download` processes after cancel and broken deep links.

**Note:** This repo has **no Ollama runtime**. GGUF is served by **llamacpp**; safetensors by **vllm** (not “ollama”).

## Workflow steps (from user)

1. Clear runtime installations  
2. Install vllm + ollama (→ **llamacpp** + vllm) via dashboard with proper config  
3. Pull small models (&lt;2GB) per runtime format (GGUF + safetensors) via dashboard  
4. Create 3 configs (2 GGUF, 1 vllm)  
5. Serve each separately  
6. Try serving two at once  
7. Test switch + timing  
8. Check for dead/orphan processes  

---

## Step results

### 1. Clear runtime installations

- **Expected:** All runtimes uninstalled (optionally purged).  
- **Observed:** API showed `llamacpp`, `vllm`, `stub-runtime` all `installed: false` already. No uninstall clicks needed.  
- **Result:** pass  

### 2. Install runtimes (dashboard)

- **Expected:** vllm + ollama/llamacpp install from UI with sensible defaults.  
- **Observed:**  
  - **llamacpp:** Dashboard Install → job `runtime_install` succeeded (~few minutes, cmake build).  
  - **vllm:** Dashboard Install (`--yes` only) → **failed** (`vllm==0.8.5` not available on Python 3.14 in runtime venv).  
  - **CLI workaround:** `loco runtime install vllm --yes -p vllm_version=0.21.0 -p pip_extra=cuda` succeeded (~5 min).  
  - Dashboard install API exposes **no build params** (flavor, vllm_version, pip_extra).  
- **Result:** partial (llamacpp pass; vllm fail in UI, pass via CLI)  

### 3. Pull small models (dashboard)

- **Expected:** Pull &lt;2GB GGUF + safetensors; models appear in table.  
- **Observed:**  
  - Cancelled stale 35B `model_pull` job (was still **running** in API; cancel on zombie job returned `JOB_NOT_CANCELABLE` briefly).  
  - Pulled via API (same as UI POST `/models/pull`):  
    - GGUF: `Qwen2.5-0.5B-Instruct-GGUF` / `qwen2.5-0.5b-instruct-q4_k_m.gguf`  
    - Safetensors: `Qwen/Qwen2.5-0.5B-Instruct`  
  - Both registered: `qwen-qwen2.5-0.5b-instruct__qwen2.5-0.5b-instruct-q4-k-m`, `qwen-qwen2.5-0.5b-instruct`.  
  - Jobs tray showed 3 concurrent jobs; models table **empty until pulls finished** (no in-progress row).  
- **Result:** pass (pulls); ux issues noted  

### 4. Create 3 configs

- **Expected:** 2 GGUF (llamacpp) + 1 vllm, realistic for local setup.  
- **Observed:** Created via API (wizard not fully exercised; `/configs/new` **404** on hard refresh):  
  - `llamacpp__qwen-0.5b__default` — port 8080, `n_gpu_layers: -1`, `ctx: 4096`  
  - `llamacpp__qwen-0.5b__alt` — port 8081, `n_gpu_layers: 0`, `ctx: 2048`  
  - `vllm__qwen-0.5b__default` — port 8000, `dtype: auto`, `max_model_len: 4096`  
- **Instance page** start dropdown initially **omitted** new configs (stale React Query / needed navigation refresh).  
- **Result:** pass (configs exist); ux partial  

### 5. Serve each separately

- **Expected:** Start/stop each config from dashboard without errors.  
- **Observed:**  
  - First start **failed** until `repo_root` set to `/home/melih/.loco/install` via `PUT /api/settings/repo_root` (Hermes layout: `repo_root` optional in yaml but **required** for param template expansion — `NoneType.as_posix()`).  
  - After fix, API start jobs (`/api/instance/start`):  

    | Config | Job time | Notes |
    |--------|----------|--------|
    | `llamacpp__qwen-0.5b__default` | ~2.1s | background, port 8080 |
    | `llamacpp__qwen-0.5b__alt` | ~2.0s | port 8081 |
    | `vllm__qwen-0.5b__default` | ~98s | vLLM cold start |

  - `loco stop` cleaned llama-server; no vllm left running after last test stop.  
- **Result:** pass after settings fix; **blocker** without `repo_root`  

### 6. Serve two at once

- **Expected:** Clear rejection; only one instance.  
- **Observed:** With `llamacpp__qwen-0.5b__default` running, second start (`vllm__qwen-0.5b__default`) returned a job but **failed** (`serve exited with code 1`). Instance unchanged (still first config). Only **one** `llama-server` process.  
- **UX:** UI still fires “Job started” for the failed second start; error only in job sheet.  
- **Result:** pass (no dual serve); ux fail  

### 7. Switch mechanism + timing

- **Expected:** Switch from dashboard; reasonable downtime.  
- **Observed:** API `POST /instance/switch` `llamacpp__qwen-0.5b__default` → `llamacpp__qwen-0.5b__alt`: **~2.1s**, job succeeded, single `llama-server` on port **8081**.  
- **Browser:** While API said `running: false`, Instance page briefly still showed “Running … alt” with **empty** “Switch to…” dropdown (no other configs listed).  
- **Result:** pass (API switch); ux fail (stale/empty switch list)  

### 8. Processes / orphans

- **Expected:** No servers or downloads left after stop/cancel.  
- **Observed:**  
  - After `loco stop`: **no** `llama-server` / `vllm` processes.  
  - **Two** `hf download` processes for **cancelled** 35B model still running (PIDs 3183, 3376, ~2.8GB RAM each) — **orphans**.  
- **Result:** fail (orphan downloads)  

---

## Findings

| ID | Severity | Area | Title | Description | Evidence |
|----|----------|------|-------|-------------|----------|
| F1 | blocker | Serve | `repo_root` None breaks serve | `loco serve` / instance start fails: `'NoneType' object has no attribute 'as_posix'` in `_settings_tokens` when `repo_root` unset in user config. | CLI traceback; job `INTERNAL_ERROR` before settings fix |
| F2 | blocker | Dashboard SPA | Deep links return 404 JSON | `/models`, `/configs/new`, `/instance` hard refresh → `{"detail":"Not Found"}`. In-app links work. Fix exists in repo (`SPAStaticFiles`) but **not in running dist**. | Browser + navigate |
| F3 | bug | Jobs | Cancelled model_pull leaves `hf download` running | Job status `cancelled` but child `hf download` processes continue. | `ps aux` PIDs 3183, 3376 |
| F4 | bug | Runtime install | vloco dashboard install fails on Py3.14 | Default `vllm==0.8.5` incompatible with Python 3.14 venv; no UI to pass `vllm_version`. | Job log `cc9b3b7c…` |
| F5 | ux | Runtime install | No build-parameter UI | Install always `loco runtime install <id> --yes`; cannot pick cpu/cuda flavor or vllm version from dashboard. | `runtimes.py` install route |
| F6 | ux | Models | No in-progress row in models table | Active pulls only visible in Jobs tray; table stays empty. | Models page during pulls |
| F7 | ux | Instance | Start/switch dropdown stale or incomplete | New configs missing from start list until refresh; switch list empty while running. | Instance snapshot |
| F8 | ux | Jobs | Second start shows generic failure | Concurrent start job fails with `serve exited with code 1` instead of `INSTANCE_ALREADY_RUNNING` (or similar). | Job `74a0d403…` |
| F9 | ux | Jobs | Job detail title is raw UUID | Sheet title `801ea69e…` not human-readable (fix in source, not deployed). | Job sheet |
| F10 | nit | Product | No Ollama runtime | User asked for ollama; repo only has `llamacpp`, `vllm`, `stub-runtime`. | `runtimes/` tree |
| F11 | opinion | Instance | vLLM start ~98s | Acceptable for cold start but UI gives little progress feedback during `instance_start_wait`. | Timed API start |

---

## Opinions (non-blocking)

- Parallel **runtime installs** (llamacpp + vllm) plus **two model pulls** hammer disk/CPU; Jobs tray helps but a single “queue” or warning would reduce surprise.  
- Using the **same GGUF file** on two configs (ports 8080/8081) is fine for testing switch; labeling configs by port in the UI would help.  
- **Settings → repo_root** should be documented on Instance page when serve fails, or defaulted to `install_root()` for Hermes installs.  

---

## API / console notes

- Orphan downloads: `hf download HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive …` ×2 after cancel.  
- Successful serve PIDs: `llama-server` on 8080/8081; vllm process during vloco config run (stopped cleanly).  

---

## Decision table (user)

| ID | Title | Suggested action | Your call |
|----|-------|------------------|-----------|
| F1 | repo_root None breaks serve | fix | |
| F2 | Deep links 404 | fix (rebuild dashboard) | |
| F3 | Orphan hf after cancel | fix | |
| F4 | vllm install Py3.14 / version pin | fix | |
| F5 | No build-param UI for runtime install | fix / discuss | |
| F6 | Models table in-progress state | fix | |
| F7 | Instance dropdown stale | fix | |
| F8 | Unclear dual-start error | fix | |
| F9 | Job sheet UUID title | fix (rebuild dashboard) | |
| F10 | No Ollama runtime | leave / docs | |
| F11 | Long vLLM start feedback | discuss | |

---

_Report generated by the dashboard-workflow-test skill. Implement only items marked **fix**._
