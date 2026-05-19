"""Hybrid prompts: questionary on TTY, plain Rich prompts otherwise."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from rich.console import Console
from rich.prompt import Prompt

from llm_cli.core.param_grid_build import cells_from_specs
from llm_cli.core.param_grid_models import MetaField, ParamGridResult
from llm_cli.core.param_grid_theme import DEFAULT_THEME, ParamGridTheme
from llm_cli.core.params import ParamSpec, ParamType

Choice = str

_FORCE_PLAIN = False
_console = Console()

_MISSING_QUESTIONARY_WARNED = False


def reset_optional_warnings() -> None:
    """Clear process-global UX hints (for tests)."""
    global _MISSING_QUESTIONARY_WARNED
    _MISSING_QUESTIONARY_WARNED = False


def _maybe_tip_missing_questionary() -> None:
    """Suggest installing questionary when running interactively without it."""
    global _MISSING_QUESTIONARY_WARNED
    if _MISSING_QUESTIONARY_WARNED:
        return
    _MISSING_QUESTIONARY_WARNED = True
    if (
        sys.stdout.isatty()
        and os.environ.get("TERM", "").strip().lower() not in ("", "dumb")
    ):
        _console.print(
            "[dim]Tip: install optional dependency "
            "`questionary` for arrow-key menus "
            "(e.g. `pip install -e .` from this repo).[/dim]"
        )


def _get_questionary() -> Any | None:
    """Return `questionary` if installed; avoids crashing when deps are stale."""
    try:
        import questionary

        return questionary
    except ImportError:
        return None


def force_plain(flag: bool) -> None:
    """Disable arrow-key UI (used by tests / `--quiet` callers when wired)."""
    global _FORCE_PLAIN
    _FORCE_PLAIN = flag


def use_plain_prompts() -> bool:
    if _FORCE_PLAIN:
        return True
    if not sys.stdout.isatty():
        return True
    term = os.environ.get("TERM", "").strip().lower()
    return term in ("", "dumb")


def text(
    prompt: str,
    *,
    default: str | None = None,
    validate: Callable[[str], str | None] | None = None,
) -> str:
    """Single-line text entry."""
    while True:
        answer = Prompt.ask(prompt, default=default)
        if answer is None:
            answer = ""
        if validate is None:
            return answer
        err = validate(answer)
        if err is None:
            return answer
        _console.print(f"[red]error:[/red] {err}")


def _confirm_plain(prompt: str, *, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw = Prompt.ask(f"{prompt} {suffix}", default="")
    token = str(raw).strip().lower()
    if token == "":
        return default
    if token in ("y", "yes"):
        return True
    if token in ("n", "no"):
        return False
    return default


def confirm(prompt: str, *, default: bool = True) -> bool:
    q = _get_questionary()
    if use_plain_prompts() or q is None:
        if q is None and not use_plain_prompts():
            _maybe_tip_missing_questionary()
        return _confirm_plain(prompt, default=default)
    result = q.confirm(prompt, default=default).ask()
    if result is None:
        raise KeyboardInterrupt
    return bool(result)


def select(
    prompt: str,
    choices: Iterable[Choice],
    *,
    default: Choice | None = None,
) -> Choice:
    choice_list = list(choices)
    if not choice_list:
        raise ValueError("select() requires at least one choice")

    if use_plain_prompts():
        _console.print(f"\n{prompt}")
        for i, c in enumerate(choice_list, start=1):
            marker = " <default>" if c == default else ""
            _console.print(f"  [{i}] {c}{marker}")
        default_str = (
            str(choice_list.index(default) + 1) if default in choice_list else None
        )
        while True:
            raw = Prompt.ask("Enter number", default=default_str)
            try:
                idx = int(str(raw).strip())
            except ValueError:
                continue
            if 1 <= idx <= len(choice_list):
                return choice_list[idx - 1]

    import questionary

    picked = questionary.select(prompt, choices=choice_list, default=default).ask()
    if picked is None:
        raise KeyboardInterrupt
    return picked


def checkbox(
    prompt: str,
    choices: Iterable[Choice],
    *,
    defaults: tuple[Choice, ...] = (),
) -> tuple[Choice, ...]:
    choice_list = list(choices)
    if use_plain_prompts():
        _console.print(f"\n{prompt}")
        _console.print("Comma-separated indices (empty = none):")
        for i, c in enumerate(choice_list, start=1):
            marker = " [default]" if c in defaults else ""
            _console.print(f"  [{i}] {c}{marker}")
        default_str = ",".join(
            str(choice_list.index(d) + 1) for d in defaults if d in choice_list
        )
        raw = Prompt.ask(">", default=default_str)
        if not str(raw).strip():
            return ()
        picked: list[Choice] = []
        for token in str(raw).split(","):
            t = token.strip()
            if not t:
                continue
            try:
                idx = int(t)
            except ValueError:
                continue
            if 1 <= idx <= len(choice_list):
                picked.append(choice_list[idx - 1])
        return tuple(picked)

    import questionary

    sel = questionary.checkbox(prompt, choices=choice_list).ask()
    if sel is None:
        raise KeyboardInterrupt
    return tuple(sel)


SAVE_SENTINEL = "save"
ABORT_SENTINEL = "abort"

RowsInput = list[tuple[str, str]] | Callable[[], list[tuple[str, str]]]


def review(
    rows: RowsInput,
    *,
    on_edit: Callable[[str], None],
) -> str:
    """Render rows in the param grid and return SAVE/ABORT sentinels."""
    row_list = rows() if callable(rows) else rows
    specs: list[ParamSpec] = []
    values: dict[str, str] = {}
    labels_by_key: dict[str, str] = {}

    for idx, (label, value) in enumerate(row_list):
        key = f"row_{idx}"
        labels_by_key[key] = label
        specs.append(
            ParamSpec(
                key=key,
                type=ParamType.STRING,
                prompt=label,
                description="",
            )
        )
        values[key] = str(value)

    result = edit_params(specs, title="Review", values=values)
    if result.action == "abort":
        return ABORT_SENTINEL

    # Keep the callback contract for legacy callers that react to edited labels.
    for key, label in labels_by_key.items():
        if result.values.get(key, "") != values.get(key, ""):
            on_edit(label)
    return SAVE_SENTINEL


@dataclass
class WalkTierResult:
    values: dict[str, str] = field(default_factory=dict)
    advanced_revealed: bool = False
    aborted: bool = False


def edit_params(
    specs: list[Any],
    *,
    title: str,
    values: dict[str, str] | None = None,
    skip_keys: set[str] | None = None,
    readonly_keys: set[str] | None = None,
    hints: dict[str, str] | None = None,
    meta: list[MetaField] | None = None,
    theme: ParamGridTheme | None = None,
) -> ParamGridResult:
    """Run the param grid over specs (defer import to avoid cycles with ``param_grid``)."""
    from llm_cli.core.param_grid import run_param_grid

    cells = cells_from_specs(
        specs,
        values=values,
        skip_keys=skip_keys,
        readonly_keys=readonly_keys,
        hints=hints,
    )
    meta_fields = meta if meta is not None else []
    theme_resolved = DEFAULT_THEME if theme is None else theme
    return run_param_grid(
        cells,
        meta_fields,
        specs=specs,
        title=title,
        theme=theme_resolved,
    )


def walk_tier(specs: list[Any]) -> WalkTierResult:
    """Prompt for common-tier ParamSpecs via the grid; advanced rows after toggle."""
    result = edit_params(specs, title="Parameters")
    if result.action == "abort":
        return WalkTierResult(
            values={},
            advanced_revealed=result.advanced_revealed,
            aborted=True,
        )
    values = dict(result.values)
    # Match sequential behaviour: omit advanced-tier keys unless advanced was visible on save.
    if not result.advanced_revealed:
        skip = {
            getattr(s, "key", "") for s in specs if getattr(s, "tier", "common") == "advanced"
        }
        values = {k: v for k, v in values.items() if k not in skip}
    return WalkTierResult(values=values, advanced_revealed=result.advanced_revealed)
