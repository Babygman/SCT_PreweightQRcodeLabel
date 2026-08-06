"""Add fields required by mock production documents.

Revision ID: 8c27d4e6f1a2
Revises: 43f8329127b0
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision = "8c27d4e6f1a2"
down_revision = "43f8329127b0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("formulas") as batch_op:
        batch_op.add_column(sa.Column("production_lot", sa.Unicode(length=100), nullable=True))
        batch_op.add_column(sa.Column("batch_quantity", sa.Numeric(18, 3), nullable=True))

    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.add_column(sa.Column("quantity", sa.Numeric(18, 3), nullable=True))
        batch_op.add_column(
            sa.Column(
                "production_date", sa.Date().with_variant(mssql.DATE(), "mssql"), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                "expected_finish_date",
                sa.Date().with_variant(mssql.DATE(), "mssql"),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.drop_column("expected_finish_date")
        batch_op.drop_column("production_date")
        batch_op.drop_column("quantity")

    with op.batch_alter_table("formulas") as batch_op:
        batch_op.drop_column("batch_quantity")
        batch_op.drop_column("production_lot")
