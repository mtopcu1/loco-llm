"""Unit tests for ParamGridTheme."""

import pytest


def test_default_theme_exposes_semantic_fields():
    from llm_cli.core.param_grid_theme import DEFAULT_THEME, ParamGridTheme

    t = DEFAULT_THEME
    assert isinstance(t, ParamGridTheme)
    assert t.modified_fg.startswith("#")
    style = t.to_prompt_toolkit_style()
    modified = style["cell-modified"]
    assert t.modified_fg.lower() in modified.lower()


def test_custom_theme_overrides():
    from llm_cli.core.param_grid_theme import ParamGridTheme

    t = ParamGridTheme(modified_fg="#FF0000")
    assert t.modified_fg == "#FF0000"


def test_rich_modified_markup():
    from llm_cli.core.param_grid_theme import DEFAULT_THEME

    assert DEFAULT_THEME.rich("modified") == "[#6BCB77]"


def test_to_prompt_toolkit_style_has_expected_classes():
    from llm_cli.core.param_grid_theme import DEFAULT_THEME

    s = DEFAULT_THEME.to_prompt_toolkit_style()
    for key in (
        "cell-default",
        "cell-modified",
        "cell-readonly",
        "cell-focus",
        "header-advanced",
        "header-common",
        "border-common",
        "border-advanced",
        "hint",
        "error",
        "meta-label",
        "text",
        "text-dim",
    ):
        assert key in s
        assert s[key]


def test_rich_unknown_role():
    from llm_cli.core.param_grid_theme import DEFAULT_THEME

    with pytest.raises(ValueError, match="unknown rich role"):
        DEFAULT_THEME.rich("not-a-role")
