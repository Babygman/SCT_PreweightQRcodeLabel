from pathlib import Path

MIGRATION = Path("migrations/versions/d2f4a6b8c0e1_add_finish_goods_master.py")
PRODUCT_LOT_MIGRATION = Path(
    "migrations/versions/f3a6c9e2b7d1_add_product_lot_business_key.py"
)


def test_finish_goods_migration_is_additive_and_chained():
    source = MIGRATION.read_text()
    assert 'revision = "d2f4a6b8c0e1"' in source
    assert 'down_revision = "b0551011c146"' in source
    for table in (
        "finish_goods_profiles",
        "finish_goods_import_batches",
        "finish_goods_import_rows",
        "production_order_product_snapshots",
    ):
        assert f'"{table}"' in source
    assert "drop_column" not in source
    assert "alter_column" not in source
    assert "UPDATE " not in source


def test_product_lot_migration_is_additive_and_chained():
    source = PRODUCT_LOT_MIGRATION.read_text()
    assert 'revision = "f3a6c9e2b7d1"' in source
    assert 'down_revision = "d2f4a6b8c0e1"' in source
    assert "production_lot_normalized" in source
    assert "uq_production_orders_product_lot_normalized" in source
    assert "drop_table" not in source
