# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

LocalLLM (`loco-llm-cli`) is a Python CLI + optional web dashboard for managing local LLM runtimes. No external services (databases, Docker, etc.) are needed — all state is file-based.

### Services

| Service | Command | Port | Notes |
|---------|---------|------|-------|
| Python CLI | `source .venv/bin/activate && llm <cmd>` | N/A | Set `LOCO_LLM_HOME=/workspace` for repo-relative state |
| FastAPI backend | `uvicorn llm_cli.webapi.app:create_app --factory --host 0.0.0.0 --port 7878` | 7878 | Requires venv activated and `LOCO_LLM_HOME` set |
| Vite dashboard | `cd dashboard && npm run dev` | 5173 | Proxies `/api` to backend at 127.0.0.1:7878 |

### Non-obvious caveats

- **Host header validation**: The FastAPI backend validates the `Host` header. When running both Vite dev server and backend, set `LLM_DASHBOARD_ALLOWED_HOSTS="127.0.0.1:7878,localhost:7878,localhost:5173,127.0.0.1:5173"` on the backend process so the Vite proxy requests are accepted.
- **Background serve mode**: `llm serve <config>` (background mode) requires either a proper init system or nohup support. In Cloud VMs without systemd, use `--foreground` or run the serve process in a tmux session.
- **Stub runtime**: For smoke testing the serve lifecycle without real model weights, use `llm runtime install stub-runtime --yes` then `llm serve stub-runtime__default --foreground`.
- **LOCO_LLM_HOME**: Always export `LOCO_LLM_HOME=/workspace` before running `llm` commands so it resolves runtimes/configs from the working tree.

### Standard commands

See `docs/DEVELOPMENT.md` for full dev workflow. Quick reference:

- **Tests (Python)**: `uv run pytest -q` (631 tests, ~30s)
- **Tests (Dashboard)**: `cd dashboard && npx vitest run` (83 tests, ~4s)
- **Lint (Dashboard)**: `cd dashboard && npx eslint .` (pre-existing errors in test-utils — not blockers)
- **Type-check (Dashboard)**: `cd dashboard && npx tsc --noEmit`
- **CLI version check**: `llm --version`
