import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARENT = "f3a6c9e2b7d1"
HEAD = "a6d8e1f3b5c7"


def migration(database, command, revision, *, database_url=None):
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url or f"sqlite:///{database}"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flask",
            "--app",
            "run.py",
            "db",
            command,
            revision,
            *(["--sql"] if database_url else []),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_upgrade_preserves_existing_rows_nullable_and_downgrade_removes_columns(tmp_path):
    database = tmp_path / "mock-provenance.sqlite"
    migration(database, "upgrade", PARENT)
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO products(id,code,name,is_active) VALUES(901,'FG','FG',1)")
        connection.execute(
            "INSERT INTO production_orders"
            "(id,po_no,product_id,production_lot,production_lot_normalized,status) "
            "VALUES(901,'LEGACY',901,'LOT','LOT','OPEN')"
        )
    migration(database, "upgrade", "head")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == HEAD
        assert connection.execute(
            "SELECT document_origin,created_at_utc FROM production_orders WHERE id=901"
        ).fetchone() == (None, None)
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(production_orders)")}
        assert "ix_production_orders_document_origin_created" in indexes
    migration(database, "downgrade", PARENT)
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(production_orders)")}
        assert "document_origin" not in columns
        assert "created_at_utc" not in columns
        legacy_po = connection.execute(
            "SELECT po_no FROM production_orders WHERE id=901"
        ).fetchone()
        assert legacy_po == (
            "LEGACY",
        )
    migration(database, "upgrade", "head")


def test_provenance_migration_compiles_offline_for_postgresql_and_sql_server(tmp_path):
    urls = {
        "postgresql": "postgresql+psycopg://offline:offline@localhost/offline",
        "mssql": (
            "mssql+pyodbc://offline:offline@localhost/offline?"
            "driver=ODBC+Driver+18+for+SQL+Server"
        ),
    }
    for dialect, database_url in urls.items():
        upgrade_ddl = migration(
            tmp_path / "unused.sqlite",
            "upgrade",
            f"{PARENT}:{HEAD}",
            database_url=database_url,
        )
        downgrade_ddl = migration(
            tmp_path / "unused.sqlite",
            "downgrade",
            f"{HEAD}:{PARENT}",
            database_url=database_url,
        )
        assert "document_origin" in upgrade_ddl, dialect
        assert "created_at_utc" in upgrade_ddl, dialect
        assert "ix_production_orders_document_origin_created" in upgrade_ddl, dialect
        assert "document_origin" in downgrade_ddl, dialect
        assert "created_at_utc" in downgrade_ddl, dialect
        assert "ix_production_orders_document_origin_created" in downgrade_ddl, dialect
