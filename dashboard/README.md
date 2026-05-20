# LocalLLM Dashboard (React SPA)

The web frontend for the LocalLLM CLI dashboard. Source code lives here; built
output is committed to `.gitignore` and emitted by `npm run build` to `dist/`.

## Dev loop

```bash
# Terminal 1 — backend with auto-reload
uv run uvicorn llm_cli.webapi.app:create_app --factory --reload --port 7878

# Terminal 2 — frontend with HMR
cd dashboard && npm run dev
# Opens http://localhost:5173; /api/* proxied to :7878
```

## Regenerating the typed API client

After changing any FastAPI route or schema in `src/llm_cli/webapi/`:

```bash
scripts/regen-api-client.sh
```

Commit the changes to `dashboard/src/api/generated.ts`. CI enforces sync via
`scripts/regen-api-client.sh --check`.

## Stack

- React 19 + TypeScript
- Vite + Tailwind CSS v4 + shadcn/ui
- TanStack Router (type-safe routes) + TanStack Query (server state)
- Zustand (cross-page client state)
- sonner (toasts)
- Vitest + Testing Library + msw (tests)

## Running tests

```bash
npm run test          # one-shot
npm run test:watch    # watch mode
npm run typecheck     # tsc --noEmit
```
