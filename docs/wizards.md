# Wizards & advisor

Release **0.2** adds guided flows alongside existing one-shot commands.

## When to use which

| Goal | Wizard | One-shot |
|---|---|---|
| First-time setup end-to-end | `llm setup` | `llm setup --default` |
| Install or register a runtime | `llm runtime setup` | `llm runtime install <id>` |
| Scaffold a launch config | `llm config setup` | `llm config new --runtime X --model Y --param k=v` |
| VRAM-aware suggestions | `llm advisor` | `llm advisor --runtime X --model Y --json` |

## `llm setup`

Writes machine settings, then offers a Y/n chain: runtime → HF URL → config → background serve. `--default` skips interactive settings prompts and the chain (only prints recommended next steps).

## `llm runtime setup`

- **Preset** — pick an official runtime (`kind: official`); delegates to the same install flow as `llm runtime install`.
- **Custom** — generate `runtimes/<id>/` with `kind: custom`, `params.yaml`, wrapped `serve.sh`, template `healthcheck.sh`, and `.installed` (no build).

## `llm config setup`

Walks serve params (common tier first; advanced behind a confirm), shows `llm advisor`-style suggestions where available, then a review screen before writing YAML.

## `llm advisor`

Three forms: interactive (pick runtime + model), `llm advisor <config-id>`, or `--runtime` / `--model`. `--json` prints machine + recommendations. After plain-text output, an optional prompt can open `llm config setup` with the same pair (`--json` suppresses it).

## TUI behavior

Wizards use **questionary** on a real TTY and fall back to numbered Rich prompts on non-TTY, dumb `TERM`, or when `wizards.force_plain(True)` is in effect.

## See also

- Spec: [`docs/superpowers/specs/2026-05-18-wizards-and-advisor.md`](superpowers/specs/2026-05-18-wizards-and-advisor.md)
- [`docs/add-a-runtime.md`](add-a-runtime.md)
- [`docs/add-a-recommendation.md`](add-a-recommendation.md)
