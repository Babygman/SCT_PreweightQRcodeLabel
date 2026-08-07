import subprocess

import pytest

from scripts.secure_migration_db import (
    KEYCHAIN_ACCOUNT,
    CredentialUnavailableError,
    keychain_password,
    migration_url,
)


def test_keychain_password_uses_project_item_without_shell(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="safe-secret\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert keychain_password() == "safe-secret"
    command, options = calls[0]
    assert command[0] == "security"
    assert command[-1] == "-w"
    assert "safe-secret" not in command
    assert options["capture_output"] is True


def test_keychain_password_fails_safely_without_echoing_tool_output(monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 44, stdout="", stderr="sensitive-detail")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(CredentialUnavailableError) as error:
        keychain_password()

    assert "sensitive-detail" not in str(error.value)


def test_migration_url_reuses_target_and_encodes_password():
    result = migration_url(
        "mssql+pyodbc://runtime:old@db.example/SCT_Preweight?driver=ODBC+Driver+18+for+SQL+Server",
        "p@ss:/?#%&+",
    )

    assert KEYCHAIN_ACCOUNT in result
    assert "runtime:old" not in result
    assert "p@ss:/?#%&+" not in result
    assert "SCT_Preweight" in result


def test_migration_url_rejects_non_mssql_target():
    with pytest.raises(RuntimeError, match="Microsoft SQL Server"):
        migration_url("sqlite:///instance/app.db", "unused")
