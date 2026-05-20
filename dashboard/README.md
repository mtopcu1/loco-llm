# LocalLLM Dashboard

React SPA for the LocalLLM web dashboard. Built with Vite, React 19, TypeScript, Tailwind v4, and shadcn/ui.

## Development

```bash
npm ci
npm run dev
```

The dev server proxies `/api` to `http://127.0.0.1:7878` (start the backend with `llm dashboard serve`).

## Build

```bash
npm ci
npm run build
```

## API client

Regenerate the typed API client from the FastAPI OpenAPI schema:

```bash
npm run regen-client
# or from repo root:
../scripts/regen-api-client.sh
```

The `--check` mode of `regen-api-client.sh` requires `npm ci` to have been run at least once locally.

## Tests

```bash
npm run test
```
