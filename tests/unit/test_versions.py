import pytest

from llm_cli.core.versions import compare_versions, parse_version


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.2.3", (1, 2, 3)),
        ("560.94", (560, 94)),
        ("3.11", (3, 11)),
        ("0.20.0", (0, 20, 0)),
        ("12.6", (12, 6)),
        ("v1.2.3", (1, 2, 3)),  # leading 'v' tolerated
    ],
)
def test_parse_version_extracts_numeric_tuple(raw: str, expected: tuple[int, ...]) -> None:
    assert parse_version(raw) == expected


def test_parse_version_handles_prerelease_suffix() -> None:
    assert parse_version("11.4.0-rc1") == (11, 4, 0)


def test_parse_version_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_version("not-a-version")


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("1.2.3", "1.2.3", 0),
        ("1.2.3", "1.2.4", -1),
        ("1.3", "1.2.99", 1),
        ("560.94", "535.0", 1),
        ("3.11", "3.11.0", 0),  # missing components treated as 0
        ("3.10", "3.11", -1),
    ],
)
def test_compare_versions(a: str, b: str, expected: int) -> None:
    assert compare_versions(a, b) == expected
