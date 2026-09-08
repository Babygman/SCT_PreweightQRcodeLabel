import pytest

from app import create_app
from app.extensions import db
from app.models import Material, MaterialImportBatch, MaterialImportRow, User, utcnow


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def approved_materials(app):
    with app.app_context():
        importer = User(
            username="approved_material_importer",
            password_hash="isolated-test-only",
            display_name="Approved Material Importer",
        )
        db.session.add(importer)
        db.session.flush()
        now = utcnow()
        batch = MaterialImportBatch(
            original_filename="approved-materials.xlsx",
            file_sha256="a" * 64,
            status="APPLIED",
            total_rows=30,
            inserted_count=30,
            updated_count=0,
            unchanged_count=0,
            rejected_count=0,
            uploaded_by_user_id=importer.id,
            uploaded_at_utc=now,
            applied_by_user_id=importer.id,
            applied_at_utc=now,
            idempotency_key="00000000-0000-4000-8000-000000000001",
        )
        db.session.add(batch)
        db.session.flush()
        materials = []
        for number in range(1, 31):
            code = f"APPROVED-MAT-{number:03d}"
            material = Material(
                code=code,
                name=f"Approved Material {number:03d}",
                unit="kg",
                source_category_no="MAT",
                is_active=True,
            )
            materials.append(material)
            db.session.add(material)
            db.session.add(
                MaterialImportRow(
                    import_batch_id=batch.id,
                    row_number=number + 1,
                    item_code_normalized=code,
                    category_no_normalized="MAT",
                    name_normalized=material.name,
                    result="INSERT",
                )
            )
        db.session.commit()
        return [material.id for material in materials]
