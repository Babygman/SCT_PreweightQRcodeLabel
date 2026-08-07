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
    with op.batch_alter_table("stations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "material_classifications",
                sa.Unicode(length=500),
                server_default=sa.text("'GENERAL'"),
                nullable=False,
            )
        )
    with op.batch_alter_table("materials") as batch_op:
        batch_op.add_column(
            sa.Column(
                "classification",
                sa.Unicode(length=50),
                server_default=sa.text("'GENERAL'"),
                nullable=False,
            )
        )
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.add_column(sa.Column("work_set_station_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("work_set_code", sa.Unicode(length=40), nullable=True))
        batch_op.add_column(
            sa.Column("work_set_active", sa.Boolean(), server_default=sa.text("0"), nullable=False)
        )
        batch_op.add_column(sa.Column("work_set_added_at_utc", sa.DateTime(), nullable=True))
        batch_op.create_foreign_key(
            "fk_production_orders_work_set_station_id_stations",
            "stations",
            ["work_set_station_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_production_orders_active_work_set",
            ["work_set_station_id", "work_set_active"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.drop_index("ix_production_orders_active_work_set")
        batch_op.drop_constraint(
            "fk_production_orders_work_set_station_id_stations", type_="foreignkey"
        )
        batch_op.drop_column("work_set_added_at_utc")
        batch_op.drop_column("work_set_active")
        batch_op.drop_column("work_set_code")
        batch_op.drop_column("work_set_station_id")
    with op.batch_alter_table("materials") as batch_op:
        batch_op.drop_column("classification")
    with op.batch_alter_table("stations") as batch_op:
        batch_op.drop_column("material_classifications")
