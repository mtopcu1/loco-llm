---
name: dashboard-workflow-test
description: >-
  Tests loco-llm dashboard workflows in the browser, documents UX issues, bugs,
  and opinions in a structured report. Use when the user asks to test a workflow,
  debug the website, audit dashboard UX, or run an end-to-end dashboard scenario
  (e.g. pull a model, install a runtime).
---

# Dashboard workflow testing (loco-llm)

## When this applies

The user names a **workflow** and the **steps** they want exercised. Treat their step list as the source of truth for this run. Do not improvise a different path unless a step is blocked — then note the blocker and what you did instead.

Trigger phrases: "test a workflow", "test the dashboard workflow", "run the … workflow", "debug the website", "UX audit".

**This run is read-only** unless the user later says "fix" or "implement" for specific findings. Do not change code while testing.

## Prerequisites

1. Dashboard must be running: `loco dashboard serve --no-open` (default http://127.0.0.1:7878).
2. Read [docs/DASHBOARD.md](../../../docs/DASHBOARD.md) for install/serve URLs and flags.
3. Use the **cursor-ide-browser** MCP: `browser_navigate` → `browser_lock` → `browser_snapshot` before each interaction; re-snapshot after navigation or submits.
4. Deep links: prefer in-app sidebar navigation first; also try direct URLs (e.g. `/models`) — SPA fallback bugs are in scope.

If the server is down, say so and stop. Do not claim you tested the UI.

## Execution checklist

Copy and track progress:

```
Workflow: [name from user]
- [ ] Step 1: …
- [ ] Step 2: …
…
- [ ] Write report to docs/superpowers/reports/
```

For each step record:

- **Expected** (what a user would reasonably expect)
- **Observed** (what actually happened)
- **Severity**: blocker | bug | ux | nit | opinion
- **Evidence**: screenshot ref, URL, error text, API response if relevant

Probe jobs tray, toasts, empty states, confirm dialogs, and job log panel when the workflow starts background work.

## Report output (required)

Write a new file:

`docs/superpowers/reports/YYYY-MM-DD-<workflow-slug>.md`

Use [report-template.md](report-template.md). Present the report path to the user when done.

End the report with a **Decision table** the user fills in:

| ID | Title | Suggested action |
|----|-------|------------------|
| F1 | … | fix / leave / discuss |

Do **not** implement fixes until the user marks items as **fix**.

## Severity guide

| Label | Meaning |
|-------|---------|
| **blocker** | Cannot complete the workflow |
| **bug** | Wrong behavior vs spec or broken feature |
| **ux** | Confusing, hidden, or inconsistent UI |
| **nit** | Small polish |
| **opinion** | Subjective; no clear defect |

## Project-specific notes

- API is under `/api`; UI is the Vite SPA in `dashboard/`.
- Long HF URLs: use a multi-line field if present; verify full URL is submitted.
- `model_pull` / runtime install jobs: open job detail sheet; confirm logs stream.
- Known past issues (verify if still true): `/models` 404 on hard refresh; empty job logs; truncated job labels.

## Catalog (grow over time)

Named workflows live in [workflows.md](workflows.md). When the user defines a new workflow, append it there after the run so future tests stay consistent.

## Example user request

> Test a workflow: **pull-model**. Steps: open dashboard → Models → Pull from HF → paste [URL] → Pull → wait for job → confirm model appears in table.

Follow those steps literally, then deliver the report.
