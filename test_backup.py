import json
from unittest import mock
import subprocess
import pytest
import backup_configs


@pytest.fixture(name="m_logger")
def fixture_m_logger():
    """Return a logger mock to avoid name conflicts."""
    return mock.Mock()


@pytest.fixture(name="f_config")
def fixture_f_config():
    """Example configuration for tests."""
    return [
        {"src": "/etc/caddy/Caddyfile", "dst": "caddy/Caddyfile", "validate": "caddy"}
    ]


def test_get_hash_file_exists(tmp_path):
    """Ensure hashing works for a regular file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("conteudo", encoding="utf-8")

    with mock.patch("subprocess.run") as m_run:
        m_run.return_value = mock.Mock(stdout="fake_git_hash", returncode=0)
        res = backup_configs.get_hash(test_file)
        assert res is not None


def test_load_data_success(tmp_path, m_logger):
    """Test loading config and previous hashes."""
    cfg = tmp_path / "config.json"
    h_file = tmp_path / "hashes.json"
    cfg.write_text(json.dumps([{"src": "a", "dst": "b"}]), encoding="utf-8")
    h_file.write_text(json.dumps({"a": "123"}), encoding="utf-8")

    with mock.patch("backup_configs.CONFIG_FILE", str(cfg)), mock.patch(
        "backup_configs.HASH_FILE", str(h_file)
    ):
        config, old_hashes = backup_configs.load_data(m_logger)
        assert config == [{"src": "a", "dst": "b"}]
        assert old_hashes == {"a": "123"}


def test_validate_caddy_ok(tmp_path, m_logger):
    """Validate Caddyfile succeeds when caddy returns success."""
    caddy_file = tmp_path / "Caddyfile"
    caddy_file.write_text("localhost { respond 'ok' }", encoding="utf-8")
    with mock.patch("subprocess.run") as m_run:
        m_run.return_value = mock.Mock(returncode=0)
        assert backup_configs.validate_caddy(caddy_file, m_logger) is True


def test_validate_caddy_fail(tmp_path, m_logger):
    """Validate Caddyfile returns False on validation failure."""
    caddy_file = tmp_path / "Caddyfile"
    with mock.patch(
        "subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")
    ):
        assert backup_configs.validate_caddy(caddy_file, m_logger) is False
        m_logger.error.assert_called()


def test_sync_files_success(tmp_path, m_logger, f_config):
    """Test file synchronization logic using the config fixture."""
    # Prepare paths based on tmp_path to avoid touching the real disk
    src_file = tmp_path / "Caddyfile"
    src_file.write_text("localhost { respond 'ok' }", encoding="utf-8")
    repo_dir = tmp_path / "repo"
    backup_configs.GIT_PATH = repo_dir
    config = f_config
    config[0]["src"] = str(src_file)
    with mock.patch("backup_configs.validate_caddy", return_value=True):
        assert backup_configs.sync_files(config, m_logger) is True
    assert (repo_dir / config[0]["dst"]).exists()


def test_commit_changes_no_diff(m_logger):
    """Ensure commit is skipped when there are no changes."""
    with mock.patch("subprocess.run") as m_run:
        m_run.return_value = mock.Mock(stdout="", returncode=0)
        backup_configs.commit_changes(m_logger, {"a": "123"})
        m_logger.info.assert_any_call("No real changes detected by Git.")


def test_main_no_changes(m_logger):
    """Ensure main exits early when there are no hash changes."""
    with mock.patch("backup_configs.setup_logger", return_value=m_logger), mock.patch(
        "backup_configs.load_data", return_value=([{"src": "a"}], {"a": "h1"})
    ), mock.patch("backup_configs.get_hash", return_value="h1"):

        backup_configs.main()
        m_logger.info.assert_called_with("No changes detected in hashes.")


def test_main_full_flow(m_logger, f_config):
    """Test the full successful execution flow."""
    with mock.patch("backup_configs.setup_logger", return_value=m_logger), mock.patch(
        "backup_configs.load_data", return_value=(f_config, {})
    ), mock.patch("backup_configs.get_hash", return_value="new_h"), mock.patch(
        "backup_configs.sync_files", return_value=True
    ), mock.patch(
        "backup_configs.commit_changes"
    ) as m_commit:

        backup_configs.main()
        m_commit.assert_called_once()
