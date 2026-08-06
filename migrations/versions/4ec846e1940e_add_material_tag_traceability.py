"""Add Material Tag traceability to weighing transactions.

Revision ID: 4ec846e1940e
Revises: 8c27d4e6f1a2
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision = "4ec846e1940e"
down_revision = "8c27d4e6f1a2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("weighing_transactions") as batch_op:
        batch_op.alter_column(
            "raw_material_lot_id", existing_type=sa.Integer(), nullable=True
        )
        batch_op.add_column(
            sa.Column(
                "material_tag_raw_payload",
                sa.UnicodeText().with_variant(mssql.NVARCHAR(None), "mssql"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "receiving_date_snapshot",
                sa.Date().with_variant(mssql.DATE(), "mssql"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("purchase_order_snapshot", sa.Unicode(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("purchase_order_line_snapshot", sa.Unicode(length=30), nullable=True)
        )
        batch_op.add_column(
            sa.Column("material_code_snapshot", sa.Unicode(length=50), nullable=True)
        )
        batch_op.add_column(
            sa.Column("delivery_invoice_snapshot", sa.Unicode(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("vendor_lot_snapshot", sa.Unicode(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("supplier_snapshot", sa.Unicode(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("comment_snapshot", sa.Unicode(length=200), nullable=True)
        )
        batch_op.add_column(
            sa.Column("warehouse_snapshot", sa.Unicode(length=50), nullable=True)
        )
        batch_op.add_column(
            sa.Column("location_snapshot", sa.Unicode(length=50), nullable=True)
        )
        batch_op.add_column(sa.Column("shelf_snapshot", sa.Unicode(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table("weighing_transactions") as batch_op:
        batch_op.drop_column("shelf_snapshot")
        batch_op.drop_column("location_snapshot")
        batch_op.drop_column("warehouse_snapshot")
        batch_op.drop_column("comment_snapshot")
        batch_op.drop_column("supplier_snapshot")
        batch_op.drop_column("vendor_lot_snapshot")
        batch_op.drop_column("delivery_invoice_snapshot")
        batch_op.drop_column("material_code_snapshot")
        batch_op.drop_column("purchase_order_line_snapshot")
        batch_op.drop_column("purchase_order_snapshot")
        batch_op.drop_column("receiving_date_snapshot")
        batch_op.drop_column("material_tag_raw_payload")
        batch_op.alter_column(
            "raw_material_lot_id", existing_type=sa.Integer(), nullable=False
        )
