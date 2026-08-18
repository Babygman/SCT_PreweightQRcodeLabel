from pathlib import Path

MIGRATION = Path("migrations/versions/b0551011c146_add_material_tag_issuance_foundation.py")


def test_foundation_migration_is_additive_and_has_expected_parent():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "b0551011c146"' in source
    assert 'down_revision = "c8d4e6f1a2b3"' in source
    for table in (
        "material_import_batches",
        "material_import_rows",
        "material_tag_drafts",
        "material_tag_batches",
        "material_tags",
        "material_tag_print_events",
    ):
        assert f'op.create_table(\n        "{table}"' in source
    assert 'add_column(sa.Column("source_category_no"' in source
    assert "weighing_transactions" not in source
    assert "production_orders" not in source


def test_foundation_migration_documents_destructive_downgrade_warning():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "issued records" in source
    assert "separate approval" in source
