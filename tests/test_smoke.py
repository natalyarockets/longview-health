"""Smoke test -- verify the project is importable and CLI is wired up."""

from click.testing import CliRunner

from longview_health.cli.main import cli


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Longview Health" in result.output


def test_cli_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_vault_subcommands_exist() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["vault", "--help"])
    assert result.exit_code == 0
    assert "create" in result.output
    assert "list" in result.output
    assert "delete" in result.output


def test_all_top_level_commands_exist() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for cmd in ["vault", "rescan", "search", "results", "trend", "export", "review"]:
        assert cmd in result.output, f"Command '{cmd}' missing from CLI"
