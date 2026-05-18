# Param Grid List/Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 2×3 card param grid with a wizard shell (Back/Next footer), meta form step, compact param list, and detail editor; hide readonly params from navigation.

**Architecture:** Shared `wizard_shell` focus ladder; `param_grid.py` state machine (`meta` → `list` ⇄ `detail`); `filter_visible_cells` excludes readonly; plain Rich fallback mirrors two-step flow. Spec: `docs/superpowers/specs/2026-05-18-param-grid-list-detail-design.md`.

**Tech Stack:** Python 3.12+, prompt_toolkit 3, Rich, pytest.

---

## Status

Implemented in this branch:

- [x] `param_grid_layout.py` — column width, wrap, scroll helpers
- [x] `wizard_shell.py` — footer render + focus ladder
- [x] `param_grid_build.filter_visible_cells`
- [x] `param_grid.py` — list/detail TUI rewrite
- [x] `param_grid_plain.py` — two-step meta + params
- [x] Unit tests + `docs/wizards.md` update
- [x] Page nav (←/→) vs back/save (Esc/Ctrl+S) separation; dynamic footer **Save** label; Ctrl+C abort

## Verification

```bash
python -m pytest tests/unit/test_param_grid*.py tests/unit/test_wizard_shell.py -v
python -m pytest -q
```

WSL smoke (interactive TTY):

```bash
llm config setup --runtime llamacpp --model <id>
```

Expect: configuration list → Next → parameter list (no gguf_path) → Enter on row opens detail with suggestion.
