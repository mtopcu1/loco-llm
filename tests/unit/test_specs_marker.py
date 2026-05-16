import pytest

from llm_cli.core.specs import (
    SPECS_END_MARKER,
    SPECS_START_MARKER,
    MarkersMissingError,
    update_specs_markdown,
)


SCAFFOLD = f"""\
# System Specs

<!-- AUTO-GENERATED: do not edit between markers. Run `llm specs` to regenerate. -->
{SPECS_START_MARKER}
OLD CONTENT
{SPECS_END_MARKER}

## Notes
- BIOS: foo
- Power plan: bar
"""


def test_update_replaces_only_between_markers() -> None:
    new_block = "_Generated: 2026-05-15T00:00:00Z_\n\n## Host\n- **CPU:** test"
    result = update_specs_markdown(SCAFFOLD, new_block)

    assert "OLD CONTENT" not in result
    assert "## Notes" in result
    assert "BIOS: foo" in result
    assert "_Generated: 2026-05-15T00:00:00Z_" in result
    assert SPECS_START_MARKER in result
    assert SPECS_END_MARKER in result


def test_update_missing_markers_raises_unless_forced() -> None:
    no_markers = "# System Specs\n\n## Notes\nfoo\n"
    with pytest.raises(MarkersMissingError):
        update_specs_markdown(no_markers, "new block")

    forced = update_specs_markdown(no_markers, "new block", force=True)
    assert SPECS_START_MARKER in forced
    assert SPECS_END_MARKER in forced
    assert "new block" in forced


def test_update_preserves_leading_content() -> None:
    text = (
        "# Specs\n\n"
        "Some intro paragraph.\n\n"
        f"{SPECS_START_MARKER}\nOLD\n{SPECS_END_MARKER}\n\n"
        "## Notes\nstuff\n"
    )
    result = update_specs_markdown(text, "NEW")
    assert "Some intro paragraph." in result
    assert "OLD" not in result
    assert "NEW" in result


def test_update_idempotent_for_same_block() -> None:
    block = "fresh content"
    once = update_specs_markdown(SCAFFOLD, block)
    twice = update_specs_markdown(once, block)
    assert once == twice
