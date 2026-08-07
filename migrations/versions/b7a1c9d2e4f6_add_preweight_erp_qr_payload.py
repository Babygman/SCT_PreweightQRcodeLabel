"""Add immutable ERP QR payload to weighing transactions.

Revision ID: b7a1c9d2e4f6
Revises: 4ec846e1940e
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision = "b7a1c9d2e4f6"
down_revision = "4ec846e1940e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("weighing_transactions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "erp_qr_payload",
                sa.UnicodeText().with_variant(mssql.NVARCHAR(None), "mssql"),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("weighing_transactions") as batch_op:
        batch_op.drop_column("erp_qr_payload")
