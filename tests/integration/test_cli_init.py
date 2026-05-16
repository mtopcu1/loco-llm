from pathlib import Path

from typer.testing import CliRunner

from llm_cli.core.paths import load_paths
from llm_cli.main import app

runner = CliRunner()


def _write_paths(repo: Path, data_root: Path) -> None:
    (repo / "paths.yaml").write_text(
        f"data_root: {data_root}\n"
        "runtimes: ${data_root}/runtimes\n"
        "models: ${data_root}/models\n"
        "cache: ${data_root}/cache\n",
        encoding="utf-8",
    )


def test_init_creates_data_root_dirs_and_env_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data_root = tmp_path / "data"
    _write_paths(repo, data_root)

    result = runner.invoke(app, ["init"], catch_exceptions=False, env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code == 0, result.stdout
    assert (data_root / "runtimes").is_dir()
    assert (data_root / "models").is_dir()
    assert (data_root / "cache").is_dir()

    env_file = repo / ".llm-env"
    assert env_file.is_file()
    contents = env_file.read_text(encoding="utf-8")
    paths = load_paths(repo / "paths.yaml")
    for key, val in paths.to_env_dict().items():
        assert f"{key}={val}" in contents


def test_init_idempotent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data_root = tmp_path / "data"
    _write_paths(repo, data_root)

    runner.invoke(app, ["init"], env={"LLM_REPO_ROOT": str(repo)})
    result = runner.invoke(app, ["init"], env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code == 0
    assert (data_root / "runtimes").is_dir()


def test_init_missing_paths_yaml_errors(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    result = runner.invoke(app, ["init"], env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code != 0
    assert "paths.yaml" in result.stdout or "paths.yaml" in (result.stderr or "")
