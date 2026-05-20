from llm_cli.core.versions import UpdateInfo, check_for_update


def test_check_for_update_non_git(monkeypatch):
    monkeypatch.setattr("llm_cli.core.versions.current_cli_version", lambda: "1.0.0")
    def _no_scaffold():
        raise RuntimeError("no scaffold")

    monkeypatch.setattr("llm_cli.core.scaffold.scaffold_root", _no_scaffold)
    info = check_for_update()
    assert info == UpdateInfo(
        current="1.0.0", latest="1.0.0", update_available=False, release_url=None
    )


def test_check_for_update_behind(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()
    monkeypatch.setattr("llm_cli.core.scaffold.scaffold_root", lambda: root)
    monkeypatch.setattr("llm_cli.core.versions.current_cli_version", lambda: "1.0.0")
    monkeypatch.setattr("llm_cli.core.versions._is_git_clone", lambda _r: True)
    monkeypatch.setattr("llm_cli.core.versions._remote_matches_expected", lambda _r: True)
    monkeypatch.setattr("llm_cli.core.versions._fetch_remote", lambda _r: None)
    monkeypatch.setattr("llm_cli.core.versions._latest_tag", lambda _r: "v1.2.0")
    monkeypatch.setattr(
        "llm_cli.core.versions._current_state",
        lambda _r: {"kind": "tag", "ref": "v1.0.0", "sha": "abc"},
    )
    info = check_for_update()
    assert info.update_available is True
    assert info.latest == "1.2.0"
    assert info.release_url == "https://github.com/mtopcu1/loco-llm/releases/tag/v1.2.0"
