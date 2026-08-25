"""Add normalized Product and Production Lot business key.

Revision ID: f3a6c9e2b7d1
Revises: d2f4a6b8c0e1
"""

import unicodedata

import sqlalchemy as sa
from alembic import context, op

revision = "f3a6c9e2b7d1"
down_revision = "d2f4a6b8c0e1"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "uq_production_orders_product_lot_normalized"
MAX_LENGTH = 100


def _normalize(value):
    if not isinstance(value, str):
        raise RuntimeError("Production Lot backfill requires text values.")
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized:
        raise RuntimeError("Production Lot backfill found a blank value.")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise RuntimeError("Production Lot backfill found a control character.")
    business_key = normalized.upper()
    if len(normalized) > MAX_LENGTH or len(business_key) > MAX_LENGTH:
        raise RuntimeError("Production Lot backfill found a value longer than 100 characters.")
    return business_key


def _offline_backfill():
    dialect = op.get_context().dialect.name
    if dialect == "mssql":
        op.execute(
            "UPDATE production_orders SET production_lot_normalized = "
            "UPPER(LTRIM(RTRIM(production_lot)))"
        )
        op.execute(
            "IF EXISTS (SELECT 1 FROM production_orders "
            "GROUP BY product_id, production_lot_normalized HAVING COUNT(*) > 1) "
            "THROW 50001, 'Duplicate Product and normalized Production Lot detected.', 1"
        )
    else:
        op.execute(
            "UPDATE production_orders SET production_lot_normalized = "
            "UPPER(TRIM(production_lot))"
        )


def _normalized_existing_rows(connection):
    rows = connection.execute(
        sa.text("SELECT id, product_id, production_lot FROM production_orders ORDER BY id")
    ).mappings()
    normalized_rows = []
    groups = {}
    for row in rows:
        normalized = _normalize(row["production_lot"])
        normalized_rows.append((row["id"], normalized))
        groups.setdefault((row["product_id"], normalized), []).append(row["id"])
    duplicates = {key: ids for key, ids in groups.items() if len(ids) > 1}
    if duplicates:
        details = "; ".join(
            f"product_id={product_id}, lot={lot}, production_order_ids={ids}"
            for (product_id, lot), ids in sorted(duplicates.items())
        )
        raise RuntimeError("Duplicate Product and normalized Production Lot detected: " + details)
    return normalized_rows


def _online_backfill(connection, normalized_rows):
    for production_order_id, normalized in normalized_rows:
        connection.execute(
            sa.text(
                "UPDATE production_orders SET production_lot_normalized=:normalized WHERE id=:id"
            ),
            {"normalized": normalized, "id": production_order_id},
        )


def upgrade():
    connection = None
    normalized_rows = None
    if not context.is_offline_mode():
        connection = op.get_bind()
        normalized_rows = _normalized_existing_rows(connection)
    op.add_column(
        "production_orders",
        sa.Column("production_lot_normalized", sa.Unicode(100), nullable=True),
    )
    if context.is_offline_mode():
        _offline_backfill()
    else:
        _online_backfill(connection, normalized_rows)
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.alter_column(
            "production_lot_normalized",
            existing_type=sa.Unicode(100),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            CONSTRAINT_NAME,
            ["product_id", "production_lot_normalized"],
        )


def downgrade():
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.drop_constraint(CONSTRAINT_NAME, type_="unique")
        batch_op.drop_column("production_lot_normalized")
