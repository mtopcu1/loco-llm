"""Tests for hybrid TUI primitives in core/wizards.py."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from llm_cli.core import wizards


@pytest.fixture(autouse=True)
def _reset_wizard_force_plain():
    wizards.force_plain(False)
    yield
    wizards.force_plain(False)


def test_use_plain_prompts_returns_true_when_not_a_tty(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    assert wizards.use_plain_prompts() is True


def test_use_plain_prompts_returns_true_when_term_is_dumb(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("TERM", "dumb")
    assert wizards.use_plain_prompts() is True


def test_use_plain_prompts_returns_false_on_real_tty(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("TERM", "xterm-256color")
    assert wizards.use_plain_prompts() is False


def test_text_returns_default_when_user_hits_enter(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("TERM", "xterm-256color")
    with patch("llm_cli.core.wizards.Prompt.ask", return_value="8192") as ask:
        out = wizards.text("ctx", default="8192")
    assert out == "8192"
    ask.assert_called_once()


def test_select_falls_back_to_numbered_list_when_plain(monkeypatch, capsys):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    with patch("llm_cli.core.wizards.Prompt.ask", return_value="2"):
        out = wizards.select("pick one", ["alpha", "beta", "gamma"])
    assert out == "beta"


def test_select_uses_questionary_on_tty(monkeypatch):
    pytest.importorskip("questionary")
    import questionary

    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: False)

    class FakeSelect:
        def ask(self):
            return "beta"

    with patch.object(questionary, "select", return_value=FakeSelect()) as q_select:
        out = wizards.select("pick one", ["alpha", "beta", "gamma"])
    assert out == "beta"
    q_select.assert_called_once()


def test_confirm_plain_yes_default(monkeypatch):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    with patch("llm_cli.core.wizards.Prompt.ask", return_value="") as ask:
        out = wizards.confirm("ok?", default=True)
    assert out is True
    args, kwargs = ask.call_args
    assert "[Y/n]" in args[0]


def test_confirm_plain_no_input(monkeypatch):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    with patch("llm_cli.core.wizards.Prompt.ask", return_value="n"):
        out = wizards.confirm("ok?", default=True)
    assert out is False


def test_checkbox_plain_parses_comma_indices(monkeypatch):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    with patch("llm_cli.core.wizards.Prompt.ask", return_value="1,3"):
        out = wizards.checkbox("pick any", ["a", "b", "c"])
    assert out == ("a", "c")


def test_checkbox_plain_accepts_empty(monkeypatch):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    with patch("llm_cli.core.wizards.Prompt.ask", return_value=""):
        out = wizards.checkbox("pick any", ["a", "b", "c"])
    assert out == ()


def test_walk_tier_yields_common_then_offers_advanced(monkeypatch):
    from llm_cli.core.params import ParamSpec, ParamType

    specs = [
        ParamSpec(
            key="ctx",
            type=ParamType.INT,
            default=8192,
            tier="common",
            description="Context window",
        ),
        ParamSpec(
            key="extra",
            type=ParamType.STRING,
            default="",
            tier="advanced",
            description="Pass-through",
        ),
    ]
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    # Plain grid: edit row 1, toggle advanced (A), edit row 2, save (S).
    answers = iter(["1", "8192", "a", "2", "--foo", "s"])
    with patch(
        "llm_cli.core.param_grid_plain.Prompt.ask",
        side_effect=lambda *a, **k: next(answers),
    ):
        result = wizards.walk_tier(specs)
    assert result.values == {"ctx": "8192", "extra": "--foo"}
    assert result.advanced_revealed is True


def test_walk_tier_skips_advanced_when_user_declines(monkeypatch):
    from llm_cli.core.params import ParamSpec, ParamType

    specs = [
        ParamSpec(
            key="ctx",
            type=ParamType.INT,
            default=8192,
            tier="common",
            description="Context window",
        ),
        ParamSpec(
            key="extra",
            type=ParamType.STRING,
            default="",
            tier="advanced",
            description="Pass-through",
        ),
    ]
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    answers = iter(["1", "8192", "s"])
    with patch(
        "llm_cli.core.param_grid_plain.Prompt.ask",
        side_effect=lambda *a, **k: next(answers),
    ):
        result = wizards.walk_tier(specs)
    assert result.values == {"ctx": "8192"}
    assert result.advanced_revealed is False


def test_walk_tier_delegates_to_grid(monkeypatch):
    from llm_cli.core.param_grid_models import ParamGridResult
    from llm_cli.core.params import ParamSpec, ParamType

    specs = [
        ParamSpec(key="only", type=ParamType.INT, default=1, tier="common"),
    ]
    captured: dict[str, object] = {}

    def stub_edit_params(s: list[ParamSpec], **kwargs: object) -> ParamGridResult:
        captured["specs"] = s
        captured["kwargs"] = kwargs
        return ParamGridResult(
            values={"only": "2"},
            meta={},
            action="save",
            advanced_revealed=False,
        )

    monkeypatch.setattr(wizards, "edit_params", stub_edit_params)
    result = wizards.walk_tier(specs)
    assert captured["specs"] is specs
    assert captured["kwargs"]["title"] == "Parameters"
    assert result.values == {"only": "2"}
    assert result.advanced_revealed is False


def test_walk_tier_abort_from_grid_returns_empty_values(monkeypatch):
    from llm_cli.core.param_grid_models import ParamGridResult
    from llm_cli.core.params import ParamSpec, ParamType

    specs = [
        ParamSpec(key="only", type=ParamType.INT, default=1, tier="common"),
    ]

    def stub_edit_params(_specs: list[ParamSpec], **kwargs: object) -> ParamGridResult:
        return ParamGridResult(
            values={"only": "9"},
            meta={},
            action="abort",
            advanced_revealed=True,
        )

    monkeypatch.setattr(wizards, "edit_params", stub_edit_params)
    result = wizards.walk_tier(specs)
    assert result.values == {}
    assert result.advanced_revealed is True


def test_review_save_returns_save(monkeypatch):
    from llm_cli.core.param_grid_models import ParamGridResult

    rows = [("runtime", "llamacpp"), ("port", "8080")]

    monkeypatch.setattr(
        wizards,
        "edit_params",
        lambda specs, **kwargs: ParamGridResult(
            values={s.key: str(s.default or "") for s in specs},
            meta={},
            action="save",
            advanced_revealed=False,
        ),
    )
    action = wizards.review(rows, on_edit=lambda key: None)
    assert action == "save"


def test_review_abort_returns_abort(monkeypatch):
    from llm_cli.core.param_grid_models import ParamGridResult

    rows = [("runtime", "llamacpp")]

    monkeypatch.setattr(
        wizards,
        "edit_params",
        lambda specs, **kwargs: ParamGridResult(
            values={s.key: str(s.default or "") for s in specs},
            meta={},
            action="abort",
            advanced_revealed=False,
        ),
    )
    action = wizards.review(rows, on_edit=lambda key: None)
    assert action == "abort"


def test_review_edit_loops_until_save(monkeypatch):
    from llm_cli.core.param_grid_models import ParamGridResult

    rows = [("runtime", "llamacpp"), ("port", "8080")]
    edited: list[str] = []

    def stub_edit_params(specs, **kwargs):
        values = {s.key: str(s.default or "") for s in specs}
        values["row_1"] = "9090"
        return ParamGridResult(
            values=values,
            meta={},
            action="save",
            advanced_revealed=False,
        )

    monkeypatch.setattr(wizards, "edit_params", stub_edit_params)
    action = wizards.review(rows, on_edit=lambda key: edited.append(key))
    assert action == "save"
    assert edited == ["port"]
