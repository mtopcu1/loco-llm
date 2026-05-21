# Dashboard workflow report (rerun): full runtime → model → config → serve

**Date:** 2026-05-21 (rerun after fixes)  
**Tester:** Cursor agent  
**Environment:** WSL, dashboard http://127.0.0.1:7878, editable CLI from `/mnt/c/Private/Projects/local-llm-scaffold`, dist rebuilt on Windows and synced to `~/.loco/install/dashboard/dist`

## Summary

**Most prior findings are resolved** in this rerun. API checks confirm: SPA deep links return **200**, dual start returns **`INSTANCE_ALREADY_RUNNING` (409)** before spawning a job, `${repo_root}` expands to **`~/.loco/install`** when unset, switch completes in **~2s**, and no orphan `llama-server` / `hf download` processes after stop. Runtimes **llamacpp** and **vllm** were already installed from the earlier run; full reinstall/pull cycle was not repeated (would take ~10+ minutes).

## Fixes applied (this session)

| ID | Fix |
|----|-----|
| F1 | `_settings_tokens` uses `install_root()` when `repo_root` is None |
| F2 | `SPAStaticFiles` fallback (already in tree); dist rebuilt |
| F3 | Job subprocesses use new session / `killpg` (or Windows `taskkill /T`) on cancel |
| F4/F5 | `vllm` build.sh defaults `0.21.0` + `cuda`; dashboard install API passes `-p vllm_version=0.21.0 -p pip_extra=cuda` |
| F6 | Models table shows in-progress `model_pull` rows from jobs |
| F7 | Instance page refetches configs/instance on mount; start/switch invalidates instance query |
| F8 | `POST /instance/start` returns 409 if an instance is already running |
| F9 | Job sheet title uses `jobTitle()` (dist rebuild) |

## Rerun results (API + spot checks)

| Step / finding | Result |
|----------------|--------|
| Health | pass |
| F2 `/models` hard URL | **200** (HTML SPA) |
| Runtimes installed | llamacpp ✓, vllm ✓ |
| F8 dual start | **409** `INSTANCE_ALREADY_RUNNING` (no failed serve job) |
| F1 `${repo_root}` with None | expands to `/home/melih/.loco/install/runtimes` |
| Switch timing | **~2s**, succeeded |
| F3 orphans after stop | **none** (`llama-server`, `hf download`, `vllm`) |

## Not re-validated end-to-end in UI

- Full runtime uninstall → dashboard reinstall (vllm build ~5 min)
- Fresh model pulls + in-progress table rows (F6) — needs browser during an active pull
- vllm cold start (~98s) — skipped
- F10 (no Ollama) — unchanged product fact

## Decision table (rerun)

| ID | Title | Suggested action |
|----|-------|------------------|
| F1 | repo_root None breaks serve | **fixed** — leave |
| F2 | Deep links 404 | **fixed** — leave |
| F3 | Cancelled pull orphans | **fixed** — leave (re-test cancel during a live large pull) |
| F4 | vllm dashboard install Py3.14 | **fixed** (defaults) — leave |
| F5 | No build-param UI | partial (vllm defaults only) — **discuss** if full param UI wanted |
| F6 | Models table empty during pulls | **fixed** in source — verify in browser on next pull |
| F7 | Stale instance dropdown | **fixed** in source — verify in browser |
| F8 | Generic dual-start error | **fixed** — leave |
| F9 | Job title UUID | **fixed** in dist — leave |
| F10 | No Ollama runtime | leave (document) |
| F11 | vLLM start slow | leave / discuss UX progress |

## Evidence

```text
GET /models -> 200
second start HTTP 409 INSTANCE_ALREADY_RUNNING
expand: /home/melih/.loco/install/runtimes
switch status=succeeded elapsed=2s
orphan check: (none)
```

Script: `scripts/workflow_rerun_api.sh`
