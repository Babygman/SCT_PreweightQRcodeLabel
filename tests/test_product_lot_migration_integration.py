import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PARENT = "d2f4a6b8c0e1"
HEAD = "a6d8e1f3b5c7"


def migration(database, command, revision, *, check=True, database_url=None):
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
    if check and result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result


def seed(database, rows):
    with sqlite3.connect(database) as connection:
        connection.executemany(
            "INSERT INTO products(id,code,name,is_active) VALUES(?,?,?,1)",
            [(1001, "FG-A", "Product A"), (1002, "FG-B", "Product B")],
        )
        connection.executemany(
            "INSERT INTO production_orders"
            "(id,po_no,product_id,production_lot,status,work_set_active) "
            "VALUES(?,?,?,?, 'OPEN',0)",
            rows,
        )


def test_upgrade_downgrade_reupgrade_preserves_original_and_enforces_composite(tmp_path):
    database = tmp_path / "success.sqlite"
    migration(database, "upgrade", PARENT)
    seed(
        database,
        [
            (1001, "PO-A1", 1001, " L001 "),
            (1002, "PO-B1", 1002, "l001"),
            (1003, "PO-A2", 1001, "L002"),
        ],
    )
    migration(database, "upgrade", "head")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == HEAD
        assert connection.execute(
            "SELECT production_lot,production_lot_normalized FROM production_orders "
            "WHERE id>=1001 ORDER BY id"
        ).fetchall() == [(" L001 ", "L001"), ("l001", "L001"), ("L002", "L002")]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO production_orders"
                "(id,po_no,product_id,production_lot,production_lot_normalized,status) "
                "VALUES(1004,'PO-A3',1001,'L001','L001','OPEN')"
            )
    migration(database, "downgrade", PARENT)
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(production_orders)")}
        assert "production_lot_normalized" not in columns
        assert connection.execute(
            "SELECT production_lot FROM production_orders WHERE id>=1001 ORDER BY id"
        ).fetchall() == [(" L001 ",), ("l001",), ("L002",)]
    migration(database, "upgrade", "head")


def test_migration_aborts_before_schema_change_when_normalized_duplicates_exist(tmp_path):
    database = tmp_path / "duplicate.sqlite"
    migration(database, "upgrade", PARENT)
    seed(
        database,
        [(1001, "PO-A1", 1001, "L001"), (1002, "PO-A2", 1001, " l001 ")],
    )
    result = migration(database, "upgrade", "head", check=False)
    assert result.returncode != 0
    assert "Duplicate Product and normalized Production Lot detected" in result.stderr
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == PARENT
        columns = {row[1] for row in connection.execute("PRAGMA table_info(production_orders)")}
        assert "production_lot_normalized" not in columns


def test_mssql_offline_ddl_contains_only_composite_lot_uniqueness(tmp_path):
    database_url = (
        "mssql+pyodbc://offline:offline@localhost/SCT_Preweight?"
        "driver=ODBC+Driver+18+for+SQL+Server"
    )
    result = migration(
        tmp_path / "unused.sqlite",
        "upgrade",
        f"{PARENT}:{HEAD}",
        database_url=database_url,
    )
    ddl = result.stdout
    assert "UNIQUE (product_id, production_lot_normalized)" in ddl
    assert "UNIQUE (production_lot)" not in ddl
    assert "THROW 50001" in ddl
