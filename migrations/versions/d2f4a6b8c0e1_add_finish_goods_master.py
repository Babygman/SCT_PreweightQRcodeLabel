"""Add Finish Goods Master import and Production Order snapshots.

Revision ID: d2f4a6b8c0e1
Revises: b0551011c146
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision = "d2f4a6b8c0e1"
down_revision = "b0551011c146"
branch_labels = None
depends_on = None

utc_datetime = sa.DateTime().with_variant(mssql.DATETIME2(), "mssql")
bigint_id = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade():
    op.create_table(
        "finish_goods_profiles",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("source_category_no", sa.Unicode(30), nullable=False),
        sa.Column("updated_at_utc", utc_datetime),
        sa.Column("updated_by_user_id", sa.Integer()),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_finish_goods_profiles_product_id_products"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_finish_goods_profiles_updated_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("product_id", name=op.f("pk_finish_goods_profiles")),
    )
    op.create_table(
        "production_order_product_snapshots",
        sa.Column("production_order_id", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.Unicode(50), nullable=False),
        sa.Column("product_name", sa.Unicode(200), nullable=False),
        sa.ForeignKeyConstraint(
            ["production_order_id"],
            ["production_orders.id"],
            name=op.f(
                "fk_production_order_product_snapshots_production_order_id_production_orders"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "production_order_id", name=op.f("pk_production_order_product_snapshots")
        ),
    )
    op.create_table(
        "finish_goods_import_batches",
        sa.Column("id", bigint_id, autoincrement=True, nullable=False),
        sa.Column("original_filename", sa.Unicode(255), nullable=False),
        sa.Column("file_sha256", sa.Unicode(64), nullable=False),
        sa.Column("status", sa.Unicode(20), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("inserted_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rejected_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_at_utc", utc_datetime, nullable=False),
        sa.Column("applied_by_user_id", sa.Integer()),
        sa.Column("applied_at_utc", utc_datetime),
        sa.Column("idempotency_key", sa.Unicode(36), nullable=False),
        sa.Column("error_summary", sa.Unicode(1000)),
        sa.CheckConstraint(
            "status IN ('PREVIEWED', 'APPLIED', 'FAILED')",
            name=op.f("ck_finish_goods_import_batches_status"),
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            name=op.f("fk_finish_goods_import_batches_uploaded_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["applied_by_user_id"],
            ["users.id"],
            name=op.f("fk_finish_goods_import_batches_applied_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finish_goods_import_batches")),
        sa.UniqueConstraint(
            "idempotency_key", name=op.f("uq_finish_goods_import_batches_idempotency_key")
        ),
    )
    op.create_index(
        "ix_finish_goods_import_batches_file_sha256", "finish_goods_import_batches", ["file_sha256"]
    )
    op.create_table(
        "finish_goods_import_rows",
        sa.Column("id", bigint_id, autoincrement=True, nullable=False),
        sa.Column("import_batch_id", bigint_id, nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("code_normalized", sa.Unicode(50)),
        sa.Column("category_no_normalized", sa.Unicode(30)),
        sa.Column("name_normalized", sa.Unicode(200)),
        sa.Column("result", sa.Unicode(20), nullable=False),
        sa.Column("reason_code", sa.Unicode(50)),
        sa.Column("reason_detail", sa.Unicode(500)),
        sa.CheckConstraint(
            "result IN ('INSERT', 'UPDATE', 'UNCHANGED', 'REJECTED')",
            name=op.f("ck_finish_goods_import_rows_result"),
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["finish_goods_import_batches.id"],
            name=op.f("fk_finish_goods_import_rows_import_batch_id_finish_goods_import_batches"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finish_goods_import_rows")),
        sa.UniqueConstraint(
            "import_batch_id",
            "row_number",
            name=op.f("uq_finish_goods_import_rows_import_batch_id"),
        ),
    )


def downgrade():
    op.drop_table("finish_goods_import_rows")
    op.drop_index(
        "ix_finish_goods_import_batches_file_sha256", table_name="finish_goods_import_batches"
    )
    op.drop_table("finish_goods_import_batches")
    op.drop_table("production_order_product_snapshots")
    op.drop_table("finish_goods_profiles")
