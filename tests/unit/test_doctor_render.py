from llm_cli.core.doctor import (
    Requirement,
    render_requirements_md,
    render_requirements_md_grouped,
)


def test_render_requirements_md_contains_table_headers_and_rows() -> None:
    reqs = [
        Requirement(
            id="python",
            name="Python",
            why="base interpreter",
            verify_cmd="python3 --version",
            version_regex=r"Python\s+([\d.]+)",
            min_version="3.11",
            install_hint="apt install python3.11",
        ),
        Requirement(
            id="git",
            name="Git",
            why="cloning runtime forks",
            verify_cmd="git --version",
            version_regex=r"git version\s+([\d.]+)",
            min_version=None,
            install_hint="apt install git",
        ),
    ]

    md = render_requirements_md(reqs)

    assert "# External Requirements" in md
    assert "auto-generated" in md.lower()
    assert "| ID | Name | Min | Verify | Install | Why |" in md
    assert "| python |" in md
    assert "Python" in md
    assert "3.11" in md
    assert "`python3 --version`" in md
    assert "apt install python3.11" in md
    assert "| git |" in md
    assert "—" in md  # min=None rendered as em dash


def test_render_requirements_md_grouped_has_universal_and_runtime_sections() -> None:
    universal = [
        Requirement(
            id="python",
            name="Python",
            why="base",
            verify_cmd="python3 --version",
            version_regex="([\\d.]+)",
            min_version="3.11",
            install_hint="",
        )
    ]
    by_runtime = {
        "llamacpp": [
            Requirement(
                id="cmake",
                name="cmake",
                why="builds llama.cpp",
                verify_cmd="cmake --version",
                version_regex="([\\d.]+)",
                min_version="3.16",
                install_hint="apt install cmake",
            )
        ]
    }

    md = render_requirements_md_grouped(universal, by_runtime)

    assert "## Universal" in md
    assert "## Runtime: llamacpp" in md
    assert "python" in md
    assert "cmake" in md
