"""Transfer SCT_Preweight_UAT business data from SQL Server to PostgreSQL.

Export is SELECT-only and writes a mode-0600 gzip bundle. Import requires an
empty, migrated PostgreSQL UAT database and runs in one transaction. The
script intentionally excludes ``alembic_version`` from copied table data;
the PostgreSQL schema must already be at the expected application revision.
"""

import argparse
import gzip
import hashlib
import json
import os
import stat
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import func, inspect, select, text

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import app.models  # noqa: E402,F401 - registers complete metadata
from app.extensions import db  # noqa: E402

FORMAT_VERSION = 1
EXPECTED_REVISION = "f3a6c9e2b7d1"
SOURCE_DATABASE = "SCT_Preweight_UAT"
TARGET_DATABASE = "sct_preweight_uat"


class TransferError(RuntimeError):
    """Raised when a transfer safety or integrity check fails."""


def _business_tables():
    return tuple(db.metadata.sorted_tables)


def _encoded(value):
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat(timespec="microseconds")}
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"type": "decimal", "value": str(value)}
    if isinstance(value, bytes):
        return {"type": "bytes", "value": value.hex()}
    return value


def _decoded(value):
    if not isinstance(value, dict) or set(value) != {"type", "value"}:
        return value
    kind = value["type"]
    raw = value["value"]
    if kind == "datetime":
        return datetime.fromisoformat(raw)
    if kind == "date":
        return date.fromisoformat(raw)
    if kind == "decimal":
        return Decimal(raw)
    if kind == "bytes":
        return bytes.fromhex(raw)
    raise TransferError(f"Unsupported encoded value type: {kind}")


def _canonical_rows(rows):
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _row_hash(rows):
    return hashlib.sha256(_canonical_rows(rows).encode("utf-8")).hexdigest()


def _ordered_statement(table):
    primary_key = tuple(table.primary_key.columns)
    statement = select(table)
    return statement.order_by(*primary_key) if primary_key else statement


def _read_encoded_rows(connection, table):
    rows = []
    for row in connection.execute(_ordered_statement(table)).mappings():
        rows.append({column.name: _encoded(row[column.name]) for column in table.columns})
    return rows


def _database_name(connection):
    dialect = connection.dialect.name
    if dialect == "mssql":
        return connection.scalar(text("SELECT DB_NAME()"))
    if dialect == "postgresql":
        return connection.scalar(text("SELECT current_database()"))
    raise TransferError(f"Unsupported database dialect: {dialect}")


def _revision(connection):
    return connection.scalar(text("SELECT version_num FROM alembic_version"))


def _require_url(environment_name):
    value = os.environ.get(environment_name)
    if not value:
        raise TransferError(f"{environment_name} environment variable is required.")
    return value


def export_bundle(output_path):
    source_url = _require_url("SOURCE_DATABASE_URL")
    engine = sa.create_engine(source_url, isolation_level="REPEATABLE READ")
    try:
        if engine.dialect.name != "mssql":
            raise TransferError("Export source must be Microsoft SQL Server.")
        with engine.connect() as connection:
            database_name = _database_name(connection)
            if database_name != SOURCE_DATABASE:
                raise TransferError(
                    f"Refusing export from unexpected database: {database_name!r}."
                )
            revision = _revision(connection)
            if revision != EXPECTED_REVISION:
                raise TransferError(
                    f"Source Alembic revision is {revision!r}; expected {EXPECTED_REVISION!r}."
                )
            table_payloads = []
            for table in _business_tables():
                rows = _read_encoded_rows(connection, table)
                table_payloads.append(
                    {
                        "name": table.name,
                        "columns": [column.name for column in table.columns],
                        "row_count": len(rows),
                        "sha256": _row_hash(rows),
                        "rows": rows,
                    }
                )
            payload = {
                "format_version": FORMAT_VERSION,
                "source_database": database_name,
                "source_revision": revision,
                "tables": table_payloads,
            }
            connection.rollback()
    finally:
        engine.dispose()

    output_path = Path(output_path).resolve()
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with gzip.open(temporary_path, "wt", encoding="utf-8", newline="\n") as bundle:
            json.dump(payload, bundle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        os.chmod(temporary_path, stat.S_IRUSR | stat.S_IWUSR)
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"export_result=SUCCESS tables={len(table_payloads)} rows="
          f"{sum(table['row_count'] for table in table_payloads)}")
    print(f"bundle={output_path}")


def _load_bundle(path):
    path = Path(path).resolve()
    with gzip.open(path, "rt", encoding="utf-8") as bundle:
        payload = json.load(bundle)
    if payload.get("format_version") != FORMAT_VERSION:
        raise TransferError("Unsupported transfer bundle format version.")
    if payload.get("source_database") != SOURCE_DATABASE:
        raise TransferError("Transfer bundle source database is unexpected.")
    if payload.get("source_revision") != EXPECTED_REVISION:
        raise TransferError("Transfer bundle source revision is unexpected.")
    expected_tables = {table.name: table for table in _business_tables()}
    supplied_tables = {item.get("name"): item for item in payload.get("tables", [])}
    if set(supplied_tables) != set(expected_tables):
        raise TransferError("Transfer bundle table set does not match application metadata.")
    for name, table in expected_tables.items():
        item = supplied_tables[name]
        expected_columns = [column.name for column in table.columns]
        if item.get("columns") != expected_columns:
            raise TransferError(f"Column set mismatch for table {name}.")
        rows = item.get("rows")
        if not isinstance(rows, list) or item.get("row_count") != len(rows):
            raise TransferError(f"Row count metadata is invalid for table {name}.")
        if item.get("sha256") != _row_hash(rows):
            raise TransferError(f"Row hash validation failed for table {name}.")
    return payload, supplied_tables


def inspect_bundle(path):
    payload, tables = _load_bundle(path)
    print(f"bundle_result=VALID source_database={payload['source_database']} "
          f"revision={payload['source_revision']}")
    for name in sorted(tables):
        print(f"table={name} rows={tables[name]['row_count']} sha256={tables[name]['sha256']}")


def _require_empty_target(connection, tables):
    nonempty = []
    for table in tables:
        count = connection.scalar(select(func.count()).select_from(table))
        if count:
            nonempty.append(f"{table.name}={count}")
    if nonempty:
        raise TransferError("Target business tables are not empty: " + ", ".join(nonempty))


def _reset_sequence(connection, table):
    primary_key = tuple(table.primary_key.columns)
    if len(primary_key) != 1 or not isinstance(primary_key[0].type, (sa.Integer, sa.BigInteger)):
        return
    column = primary_key[0]
    sequence = connection.scalar(
        text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
        {"table_name": table.name, "column_name": column.name},
    )
    if sequence is None:
        return
    maximum = connection.scalar(select(func.max(column)))
    connection.execute(
        text("SELECT setval(CAST(:sequence AS regclass), :value, :is_called)"),
        {
            "sequence": sequence,
            "value": maximum if maximum is not None else 1,
            "is_called": maximum is not None,
        },
    )


def import_bundle(bundle_path, confirmation):
    if confirmation != TARGET_DATABASE:
        raise TransferError(f"--confirm-target must equal {TARGET_DATABASE!r}.")
    payload, supplied_tables = _load_bundle(bundle_path)
    target_url = _require_url("DATABASE_URL")
    engine = sa.create_engine(target_url)
    try:
        if engine.dialect.name != "postgresql":
            raise TransferError("Import target must be PostgreSQL.")
        with engine.begin() as connection:
            database_name = _database_name(connection)
            if database_name != TARGET_DATABASE:
                raise TransferError(
                    f"Refusing import into unexpected database: {database_name!r}."
                )
            revision = _revision(connection)
            if revision != EXPECTED_REVISION:
                raise TransferError(
                    f"Target Alembic revision is {revision!r}; expected {EXPECTED_REVISION!r}."
                )
            database_tables = set(inspect(connection).get_table_names())
            required_tables = {table.name for table in _business_tables()} | {"alembic_version"}
            if not required_tables.issubset(database_tables):
                missing = sorted(required_tables - database_tables)
                raise TransferError("Target schema is incomplete: " + ", ".join(missing))
            tables = _business_tables()
            _require_empty_target(connection, tables)
            for table in tables:
                encoded_rows = supplied_tables[table.name]["rows"]
                decoded_rows = [
                    {key: _decoded(value) for key, value in row.items()}
                    for row in encoded_rows
                ]
                if decoded_rows:
                    connection.execute(table.insert(), decoded_rows)
            for table in tables:
                _reset_sequence(connection, table)
            for table in tables:
                actual_rows = _read_encoded_rows(connection, table)
                expected = supplied_tables[table.name]
                if len(actual_rows) != expected["row_count"]:
                    raise TransferError(f"Imported row count mismatch for table {table.name}.")
                if _row_hash(actual_rows) != expected["sha256"]:
                    raise TransferError(f"Imported row hash mismatch for table {table.name}.")
    finally:
        engine.dispose()
    print(f"import_result=SUCCESS database={TARGET_DATABASE} tables={len(payload['tables'])} "
          f"rows={sum(table['row_count'] for table in payload['tables'])}")


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export_command = commands.add_parser("export", help="Read SQL Server UAT into a secure bundle.")
    export_command.add_argument("bundle")
    inspect_command = commands.add_parser("inspect", help="Validate a bundle without a database.")
    inspect_command.add_argument("bundle")
    import_command = commands.add_parser(
        "import", help="Import a bundle into empty PostgreSQL UAT."
    )
    import_command.add_argument("bundle")
    import_command.add_argument("--confirm-target", required=True)
    return parser


def main():
    arguments = _parser().parse_args()
    if arguments.command == "export":
        export_bundle(arguments.bundle)
    elif arguments.command == "inspect":
        inspect_bundle(arguments.bundle)
    else:
        import_bundle(arguments.bundle, arguments.confirm_target)


if __name__ == "__main__":
    try:
        main()
    except TransferError as error:
        print(f"transfer_result=BLOCKED reason={error}", file=sys.stderr)
        raise SystemExit(1) from error
