from pathlib import Path

import pytest

from llm_cli.core.paths import Paths, load_paths


def test_load_paths_expands_tilde_and_substitutes(tmp_path: Path) -> None:
    yaml_file = tmp_path / "paths.yaml"
    yaml_file.write_text(
        "data_root: ~/llm\n"
        "runtimes: ${data_root}/runtimes\n"
        "models: ${data_root}/models\n"
        "cache: ${data_root}/cache\n",
        encoding="utf-8",
    )

    paths = load_paths(yaml_file)

    home = Path.home()
    assert paths.data_root == home / "llm"
    assert paths.runtimes == home / "llm" / "runtimes"
    assert paths.models == home / "llm" / "models"
    assert paths.cache == home / "llm" / "cache"


def test_load_paths_supports_absolute_data_root(tmp_path: Path) -> None:
    yaml_file = tmp_path / "paths.yaml"
    yaml_file.write_text(
        "data_root: /opt/llm\n"
        "runtimes: ${data_root}/runtimes\n"
        "models: ${data_root}/models\n"
        "cache: ${data_root}/cache\n",
        encoding="utf-8",
    )

    paths = load_paths(yaml_file)

    assert paths.data_root == Path("/opt/llm")
    assert paths.runtimes == Path("/opt/llm/runtimes")


def test_load_paths_missing_required_key_raises(tmp_path: Path) -> None:
    yaml_file = tmp_path / "paths.yaml"
    yaml_file.write_text("data_root: ~/llm\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required key"):
        load_paths(yaml_file)


def test_load_paths_unresolved_variable_raises(tmp_path: Path) -> None:
    yaml_file = tmp_path / "paths.yaml"
    yaml_file.write_text(
        "data_root: ~/llm\n"
        "runtimes: ${not_a_real_var}/x\n"
        "models: ${data_root}/models\n"
        "cache: ${data_root}/cache\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unresolved variable"):
        load_paths(yaml_file)


def test_load_paths_rejects_non_mapping_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "paths.yaml"
    yaml_file.write_text("[not, a, mapping]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a mapping"):
        load_paths(yaml_file)


def test_load_paths_rejects_empty_string_value(tmp_path: Path) -> None:
    yaml_file = tmp_path / "paths.yaml"
    yaml_file.write_text(
        "data_root: ~/llm\n"
        "runtimes: ${data_root}/runtimes\n"
        "models:\n"
        "cache: ${data_root}/cache\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be a non-empty string"):
        load_paths(yaml_file)


def test_paths_to_env_dict_returns_uppercased_strings(tmp_path: Path) -> None:
    yaml_file = tmp_path / "paths.yaml"
    yaml_file.write_text(
        "data_root: /opt/llm\n"
        "runtimes: ${data_root}/runtimes\n"
        "models: ${data_root}/models\n"
        "cache: ${data_root}/cache\n",
        encoding="utf-8",
    )
    paths = load_paths(yaml_file)

    env = paths.to_env_dict()

    assert env == {
        "LLM_DATA_ROOT": "/opt/llm",
        "LLM_RUNTIMES": "/opt/llm/runtimes",
        "LLM_MODELS": "/opt/llm/models",
        "LLM_CACHE": "/opt/llm/cache",
    }
