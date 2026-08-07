"""Run migration database operations with a password held in macOS Keychain."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

KEYCHAIN_SERVICE = "SCT_PreweightQRcodeLabel.migration-db"
KEYCHAIN_ACCOUNT = "sct_preweight_uat_migration"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class CredentialUnavailableError(RuntimeError):
    """Raised when the machine-local migration credential is unavailable."""


def keychain_password() -> str:
    """Read the migration password without exposing it in arguments or output."""
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-s",
            KEYCHAIN_SERVICE,
            "-a",
            KEYCHAIN_ACCOUNT,
            "-w",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    password = result.stdout.rstrip("\n")
    if result.returncode != 0 or not password:
        raise CredentialUnavailableError(
            "Migration credential is unavailable in the configured macOS Keychain item."
        )
    return password


def migration_url(runtime_url: str, password: str) -> str:
    """Reuse the runtime server/database settings with the migration identity."""
    url = make_url(runtime_url)
    if url.get_backend_name() != "mssql":
        raise RuntimeError("Migration target must be Microsoft SQL Server.")
    return url.set(username=KEYCHAIN_ACCOUNT, password=password).render_as_string(
        hide_password=False
    )


def verified_status(database_url: str) -> tuple[str, str, str]:
    """Return sanitized database identity and Alembic revision."""
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            database = connection.scalar(text("SELECT DB_NAME()"))
            login = connection.scalar(text("SELECT ORIGINAL_LOGIN()"))
            revision = connection.scalar(text("SELECT version_num FROM dbo.alembic_version"))
    finally:
        engine.dispose()
    if database != "SCT_Preweight":
        raise RuntimeError("Refusing operation: database target is not SCT_Preweight.")
    if login != KEYCHAIN_ACCOUNT:
        raise RuntimeError("Refusing operation: migration login identity is unexpected.")
    return database, login, revision


def run_upgrade(database_url: str) -> int:
    """Run the project's normal Flask-Migrate upgrade with an in-memory URL."""
    child_environment = os.environ.copy()
    child_environment["DATABASE_URL"] = database_url
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "flask", "--app", "run.py", "db", "upgrade"],
            cwd=PROJECT_ROOT,
            env=child_environment,
            check=False,
        )
        return completed.returncode
    finally:
        child_environment.pop("DATABASE_URL", None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("check", "current", "upgrade"))
    arguments = parser.parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    runtime_url = os.environ.get("DATABASE_URL")
    if not runtime_url:
        print("DATABASE_URL is unavailable in machine-local configuration.", file=sys.stderr)
        return 2

    password = None
    database_url = None
    try:
        password = keychain_password()
        database_url = migration_url(runtime_url, password)
        database, login, revision = verified_status(database_url)
        print(f"database={database}")
        print(f"login={login}")
        print(f"revision={revision}")
        if arguments.operation == "upgrade":
            return run_upgrade(database_url)
        return 0
    except CredentialUnavailableError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    finally:
        password = None
        database_url = None


if __name__ == "__main__":
    raise SystemExit(main())
