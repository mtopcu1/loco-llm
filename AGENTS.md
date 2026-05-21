# AGENTS.md

## Cursor Cloud specific instructions

### Overview

LocalLLM (`loco-llm-cli`) is a Python CLI + optional React web dashboard for managing local LLM runtimes. Two services compose the dev environment:

| Service | Command | Port |
|---------|---------|------|
| FastAPI backend | `uv run uvicorn llm_cli.webapi.app:create_app --factory --reload --port 7878` | 7878 |
| Vite frontend | `cd dashboard && npm run dev` | 5173 |

### Running the CLI

```bash
export LOCO_LLM_HOME="/workspace"
export PATH="$HOME/.local/bin:$PATH"
uv run llm <command>
```

The `LOCO_LLM_HOME` env var tells the CLI to resolve runtimes/configs/state from the workspace checkout.

### Key dev gotcha: Host header security

The FastAPI backend validates the `Host` header. When running the Vite proxy (port 5173 → 7878), you must set:

```bash
export LLM_DASHBOARD_ALLOWED_HOSTS="127.0.0.1:7878,localhost:7878,localhost:5173"
```

Without this, the Vite proxy will receive `421 BAD_HOST_HEADER` responses.

### Running tests

- **Python:** `uv run pytest -q` (all unit, integration, and webapi tests)
- **Dashboard:** `cd dashboard && npm run test` (Vitest)
- **Typecheck:** `cd dashboard && npm run typecheck`
- **Lint:** `cd dashboard && npm run lint` (pre-existing lint errors exist in the codebase)

### Smoke-testing the CLI without a GPU

```bash
uv run llm setup --default
uv run llm runtime install stub-runtime --yes
uv run llm serve stub-runtime__default --foreground
# In another terminal: uv run llm status / uv run llm stop
```

### Commit conventions

All commits must follow Conventional Commits format (see `CONTRIBUTING.md`). `release-please` uses them for versioning.
