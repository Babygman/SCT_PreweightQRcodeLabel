import gzip
import json
from pathlib import Path

from sqlalchemy.dialects import mssql, postgresql
from sqlalchemy.schema import CreateIndex

from app.models import WeighingTransaction
from app.services.finish_goods_import import _batch_statement
from app.services.material_import import _batch_for_apply_statement
from scripts.postgresql_uat_transfer import (
    EXPECTED_REVISION,
    FORMAT_VERSION,
    SOURCE_DATABASE,
    _business_tables,
    _load_bundle,
    _row_hash,
)

ROOT = Path(__file__).resolve().parents[1]


def test_postgresql_partial_unique_index_matches_existing_database_rule():
    index = next(
        item
        for item in WeighingTransaction.__table__.indexes
        if item.name == "uq_weighing_active_formula_line"
    )
    sql = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
    assert "UNIQUE INDEX uq_weighing_active_formula_line" in sql
    assert "WHERE status IN ('COMPLETED', 'CONSUMED')" in sql


def test_import_batch_locks_compile_for_postgresql_and_sql_server():
    for statement in (_batch_for_apply_statement(1), _batch_statement(1)):
        postgresql_sql = str(statement.compile(dialect=postgresql.dialect()))
        mssql_sql = str(statement.compile(dialect=mssql.dialect()))
        assert "FOR UPDATE" in postgresql_sql
        assert "WITH (UPDLOCK, HOLDLOCK)" in mssql_sql


def test_postgresql_compose_is_private_and_does_not_run_migrations():
    compose = (ROOT / "compose.postgresql.uat.yaml").read_text(encoding="utf-8")
    assert "postgres:17-bookworm" in compose
    assert "internal: true" in compose
    assert "sct_preweight_postgresql_uat_data" in compose
    assert "ports:" not in compose
    assert "flask db" not in compose
    assert "alembic" not in compose


def test_transfer_bundle_integrity_can_be_checked_offline(tmp_path):
    tables = []
    for table in _business_tables():
        rows = []
        tables.append(
            {
                "name": table.name,
                "columns": [column.name for column in table.columns],
                "row_count": 0,
                "sha256": _row_hash(rows),
                "rows": rows,
            }
        )
    payload = {
        "format_version": FORMAT_VERSION,
        "source_database": SOURCE_DATABASE,
        "source_revision": EXPECTED_REVISION,
        "tables": tables,
    }
    bundle = tmp_path / "transfer.json.gz"
    with gzip.open(bundle, "wt", encoding="utf-8") as stream:
        json.dump(payload, stream)

    loaded, supplied = _load_bundle(bundle)

    assert loaded["source_revision"] == EXPECTED_REVISION
    assert set(supplied) == {table.name for table in _business_tables()}
