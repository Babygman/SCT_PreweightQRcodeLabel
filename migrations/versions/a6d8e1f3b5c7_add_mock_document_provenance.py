"""Add Mock ERP document provenance and creation time.

Revision ID: a6d8e1f3b5c7
Revises: f3a6c9e2b7d1
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision = "a6d8e1f3b5c7"
down_revision = "f3a6c9e2b7d1"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_production_orders_document_origin_created"


def upgrade():
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.add_column(sa.Column("document_origin", sa.Unicode(30), nullable=True))
        batch_op.add_column(
            sa.Column(
                "created_at_utc",
                sa.DateTime().with_variant(mssql.DATETIME2(), "mssql"),
                nullable=True,
            )
        )
        batch_op.create_index(
            INDEX_NAME,
            ["document_origin", "created_at_utc", "id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.drop_index(INDEX_NAME)
        batch_op.drop_column("created_at_utc")
        batch_op.drop_column("document_origin")
