"""Add material classifications and active weighing work sets.

Revision ID: c8d4e6f1a2b3
Revises: b7a1c9d2e4f6
"""

import sqlalchemy as sa
from alembic import op

revision = "c8d4e6f1a2b3"
down_revision = "b7a1c9d2e4f6"
branch_labels = None
depends_on = None


def upgrade():
    station_column = sa.Column(
        "material_classifications",
        sa.Unicode(length=500),
        server_default=sa.text("'GENERAL'"),
        nullable=True,
    )
    material_column = sa.Column(
        "classification",
        sa.Unicode(length=50),
        server_default=sa.text("'GENERAL'"),
        nullable=True,
    )
    order_columns = (
        sa.Column("work_set_station_id", sa.Integer(), nullable=True),
        sa.Column("work_set_code", sa.Unicode(length=40), nullable=True),
        sa.Column("work_set_active", sa.Boolean(), server_default=sa.text("0"), nullable=True),
        sa.Column("work_set_added_at_utc", sa.DateTime(), nullable=True),
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("stations") as batch_op:
            batch_op.add_column(station_column)
        with op.batch_alter_table("materials") as batch_op:
            batch_op.add_column(material_column)
        with op.batch_alter_table("production_orders") as batch_op:
            for column in order_columns:
                batch_op.add_column(column)
            batch_op.create_index(
                "ix_production_orders_active_work_set",
                ["work_set_station_id", "work_set_active"],
                unique=False,
            )
        return

    op.add_column("stations", station_column)
    op.add_column("materials", material_column)
    for column in order_columns:
        op.add_column("production_orders", column)
    op.create_index(
        "ix_production_orders_active_work_set",
        "production_orders",
        ["work_set_station_id", "work_set_active"],
        unique=False,
    )


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("production_orders") as batch_op:
            batch_op.drop_index("ix_production_orders_active_work_set")
            batch_op.drop_column("work_set_added_at_utc")
            batch_op.drop_column("work_set_active")
            batch_op.drop_column("work_set_code")
            batch_op.drop_column("work_set_station_id")
        with op.batch_alter_table("materials") as batch_op:
            batch_op.drop_column("classification")
        with op.batch_alter_table("stations") as batch_op:
            batch_op.drop_column("material_classifications")
        return

    op.drop_index("ix_production_orders_active_work_set", table_name="production_orders")
    op.drop_column("production_orders", "work_set_added_at_utc")
    op.drop_column("production_orders", "work_set_active")
    op.drop_column("production_orders", "work_set_code")
    op.drop_column("production_orders", "work_set_station_id")
    op.drop_column("materials", "classification")
    op.drop_column("stations", "material_classifications")
