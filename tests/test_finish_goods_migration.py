from pathlib import Path

MIGRATION = Path("migrations/versions/d2f4a6b8c0e1_add_finish_goods_master.py")


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
