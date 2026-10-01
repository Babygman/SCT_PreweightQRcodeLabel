"""Add durable weighing replacement provenance.

Revision ID: e7b9c2d4f6a8
Revises: a6d8e1f3b5c7
"""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import mssql

revision = "e7b9c2d4f6a8"
down_revision = "a6d8e1f3b5c7"
branch_labels = None
depends_on = None

ACTIVE_INDEX = "uq_weighing_active_formula_line"
REPLACES_INDEX = "ix_weighing_replaces_transaction"
SUPERSEDED_BY_INDEX = "ix_weighing_superseded_by_transaction"
DOWNGRADE_REFUSAL = (
    "Cannot downgrade e7b9c2d4f6a8 after Reweigh provenance exists; "
    "preserve replacement relationships and audit evidence."
)


def _utc_datetime():
    return sa.DateTime().with_variant(mssql.DATETIME2(), "mssql")


def upgrade():
    with op.batch_alter_table("weighing_transactions") as batch_op:
        batch_op.drop_index(ACTIVE_INDEX)
        batch_op.add_column(sa.Column("replaces_transaction_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("superseded_by_transaction_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(sa.Column("superseded_at_utc", _utc_datetime(), nullable=True))
        batch_op.add_column(sa.Column("superseded_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("supersede_reason", sa.Unicode(500), nullable=True))
        batch_op.create_foreign_key(
            "fk_weighing_replaces_transaction",
            "weighing_transactions",
            ["replaces_transaction_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_weighing_superseded_by_transaction",
            "weighing_transactions",
            ["superseded_by_transaction_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_weighing_superseded_by_user",
            "users",
            ["superseded_by_user_id"],
            ["id"],
        )
        batch_op.create_index(
            REPLACES_INDEX,
            ["replaces_transaction_id"],
            unique=True,
            mssql_where=sa.text("replaces_transaction_id IS NOT NULL"),
            postgresql_where=sa.text("replaces_transaction_id IS NOT NULL"),
            sqlite_where=sa.text("replaces_transaction_id IS NOT NULL"),
        )
        batch_op.create_index(
            SUPERSEDED_BY_INDEX,
            ["superseded_by_transaction_id"],
            unique=True,
            mssql_where=sa.text("superseded_by_transaction_id IS NOT NULL"),
            postgresql_where=sa.text("superseded_by_transaction_id IS NOT NULL"),
            sqlite_where=sa.text("superseded_by_transaction_id IS NOT NULL"),
        )
        batch_op.create_index(
            ACTIVE_INDEX,
            ["production_order_id", "formula_item_id"],
            unique=True,
            mssql_where=sa.text(
                "status IN ('COMPLETED', 'CONSUMED') AND superseded_at_utc IS NULL"
            ),
            postgresql_where=sa.text(
                "status IN ('COMPLETED', 'CONSUMED') AND superseded_at_utc IS NULL"
            ),
            sqlite_where=sa.text(
                "status IN ('COMPLETED', 'CONSUMED') AND superseded_at_utc IS NULL"
            ),
        )


def downgrade():
    predicate = (
        "replaces_transaction_id IS NOT NULL "
        "OR superseded_by_transaction_id IS NOT NULL "
        "OR superseded_at_utc IS NOT NULL "
        "OR superseded_by_user_id IS NOT NULL "
        "OR supersede_reason IS NOT NULL"
    )
    evidence = (
        "EXISTS (SELECT 1 FROM weighing_transactions WHERE "
        f"{predicate}) OR EXISTS (SELECT 1 FROM audit_logs "
        "WHERE event_type = 'WEIGHING_REPLACED')"
    )
    if context.is_offline_mode():
        dialect = context.get_context().dialect.name
        if dialect == "postgresql":
            op.execute(
                f"DO $$ BEGIN IF {evidence} "
                f"THEN RAISE EXCEPTION '{DOWNGRADE_REFUSAL}'; "
                "END IF; END $$"
            )
        elif dialect == "mssql":
            op.execute(
                f"IF {evidence} THROW 50001, '{DOWNGRADE_REFUSAL}', 1"
            )
    else:
        populated = op.get_bind().execute(
            sa.text(f"SELECT CASE WHEN {evidence} THEN 1 ELSE 0 END")
        ).scalar()
        if populated:
            raise RuntimeError(DOWNGRADE_REFUSAL)
    with op.batch_alter_table("weighing_transactions") as batch_op:
        batch_op.drop_index(ACTIVE_INDEX)
        batch_op.drop_index(SUPERSEDED_BY_INDEX)
        batch_op.drop_index(REPLACES_INDEX)
        batch_op.drop_constraint("fk_weighing_superseded_by_user", type_="foreignkey")
        batch_op.drop_constraint("fk_weighing_superseded_by_transaction", type_="foreignkey")
        batch_op.drop_constraint("fk_weighing_replaces_transaction", type_="foreignkey")
        batch_op.drop_column("supersede_reason")
        batch_op.drop_column("superseded_by_user_id")
        batch_op.drop_column("superseded_at_utc")
        batch_op.drop_column("superseded_by_transaction_id")
        batch_op.drop_column("replaces_transaction_id")
        batch_op.create_index(
            ACTIVE_INDEX,
            ["production_order_id", "formula_item_id"],
            unique=True,
            mssql_where=sa.text("status IN ('COMPLETED', 'CONSUMED')"),
            postgresql_where=sa.text("status IN ('COMPLETED', 'CONSUMED')"),
            sqlite_where=sa.text("status IN ('COMPLETED', 'CONSUMED')"),
        )
