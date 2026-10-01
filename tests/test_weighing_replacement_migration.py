import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARENT = "a6d8e1f3b5c7"
HEAD = "e7b9c2d4f6a8"


def migration(database, command, revision, *, database_url=None, check=True):
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
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def test_replacement_migration_is_nullable_additive_and_reversible(tmp_path):
    database = tmp_path / "weighing-replacement.sqlite"
    migration(database, "upgrade", PARENT)
    migration(database, "upgrade", HEAD)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == HEAD
        columns = {
            row[1]: row[3]
            for row in connection.execute("PRAGMA table_info(weighing_transactions)")
        }
        for name in (
            "replaces_transaction_id",
            "superseded_by_transaction_id",
            "superseded_at_utc",
            "superseded_by_user_id",
            "supersede_reason",
        ):
            assert columns[name] == 0
    migration(database, "downgrade", PARENT)
    with sqlite3.connect(database) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(weighing_transactions)")
        }
        assert "replaces_transaction_id" not in columns
        assert "superseded_at_utc" not in columns
    migration(database, "upgrade", HEAD)
    _assert_populated_provenance_refuses_downgrade(tmp_path)
    _assert_audit_evidence_refuses_downgrade(tmp_path)


def _assert_populated_provenance_refuses_downgrade(tmp_path):
    database = tmp_path / "populated-replacement.sqlite"
    migration(database, "upgrade", HEAD)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO users"
            "(id,username,password_hash,display_name,created_at_utc,updated_at_utc) "
            "VALUES(1,'operator','test','Operator','2026-01-01','2026-01-01')"
        )
        connection.execute("INSERT INTO stations(id,code,name) VALUES(1,'ST-1','Station')")
        connection.execute("INSERT INTO products(id,code,name) VALUES(1,'FG-1','Product')")
        connection.execute(
            "INSERT INTO materials(id,code,name,unit) "
            "VALUES(1,'MAT-1','Material','kg')"
        )
        connection.execute(
            "INSERT INTO formulas(id,code,name,product_id) VALUES(1,'FM-1','Formula',1)"
        )
        connection.execute(
            "INSERT INTO formula_items(id,formula_id,line_no,material_id,target_weight,unit) "
            "VALUES(1,1,10,1,1.000,'kg')"
        )
        connection.execute(
            "INSERT INTO production_orders"
            "(id,po_no,product_id,production_lot,production_lot_normalized,formula_id,status) "
            "VALUES(1,'PO-1',1,'LOT-1','LOT-1',1,'READY')"
        )
        base_values = "1,1,1.000,1.000,'kg',1,1,'2026-01-01','COMPLETED'"
        connection.execute(
            "INSERT INTO weighing_transactions"
            "(id,preweight_id,production_order_id,formula_item_id,target_weight_snapshot,"
            "actual_weight,unit_snapshot,station_id,weighed_by_user_id,weighed_at_utc,status) "
            f"VALUES(1,'PW-1',{base_values})"
        )
        connection.execute(
            "UPDATE weighing_transactions SET superseded_at_utc='2026-01-02',"
            "superseded_by_user_id=1,supersede_reason='Approved replacement' WHERE id=1"
        )
        connection.execute(
            "INSERT INTO weighing_transactions"
            "(id,preweight_id,production_order_id,formula_item_id,target_weight_snapshot,"
            "actual_weight,unit_snapshot,station_id,weighed_by_user_id,weighed_at_utc,status,"
            "replaces_transaction_id) "
            f"VALUES(2,'PW-2',{base_values},1)"
        )
        connection.execute(
            "UPDATE weighing_transactions SET superseded_by_transaction_id=2 WHERE id=1"
        )
    result = migration(database, "downgrade", PARENT, check=False)
    assert result.returncode != 0
    assert "Cannot downgrade e7b9c2d4f6a8" in result.stderr
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == HEAD
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(weighing_transactions)")
        }
        assert "replaces_transaction_id" in columns
        assert "superseded_by_transaction_id" in columns
        assert connection.execute(
            "SELECT replaces_transaction_id FROM weighing_transactions WHERE id=2"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT superseded_by_transaction_id,supersede_reason "
            "FROM weighing_transactions WHERE id=1"
        ).fetchone() == (2, "Approved replacement")


def _assert_audit_evidence_refuses_downgrade(tmp_path):
    database = tmp_path / "audit-only-replacement.sqlite"
    migration(database, "upgrade", HEAD)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO audit_logs"
            "(id,event_type,entity_type,entity_id,occurred_at_utc,detail) "
            "VALUES(1,'WEIGHING_REPLACED','WeighingTransaction','2',"
            "'2026-01-02','{}')"
        )
    result = migration(database, "downgrade", PARENT, check=False)
    assert result.returncode != 0
    assert "Cannot downgrade e7b9c2d4f6a8" in result.stderr
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == HEAD
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(weighing_transactions)")
        }
        assert "replaces_transaction_id" in columns
        assert connection.execute(
            "SELECT event_type,entity_id FROM audit_logs"
        ).fetchone() == ("WEIGHING_REPLACED", "2")


def test_replacement_migration_compiles_offline_for_supported_databases(tmp_path):
    urls = {
        "postgresql": "postgresql+psycopg://offline:offline@localhost/offline",
        "mssql": (
            "mssql+pyodbc://offline:offline@localhost/offline?"
            "driver=ODBC+Driver+18+for+SQL+Server"
        ),
    }
    for dialect, database_url in urls.items():
        upgrade = migration(
            tmp_path / "unused.sqlite",
            "upgrade",
            f"{PARENT}:{HEAD}",
            database_url=database_url,
        )
        downgrade = migration(
            tmp_path / "unused.sqlite",
            "downgrade",
            f"{HEAD}:{PARENT}",
            database_url=database_url,
        )
        for ddl in (upgrade.stdout, downgrade.stdout):
            assert "superseded_at_utc" in ddl
            assert "replaces_transaction_id" in ddl
            assert "uq_weighing_active_formula_line" in ddl
        assert "Cannot downgrade e7b9c2d4f6a8" in downgrade.stdout
        if dialect == "postgresql":
            assert "RAISE EXCEPTION" in downgrade.stdout
        else:
            assert "THROW 50001" in downgrade.stdout
