from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db

application = create_app("development")
with application.app_context():
    tables = set(inspect(db.engine).get_table_names())
    expected_tables = set(db.metadata.tables) | {"alembic_version"}
    if tables != expected_tables:
        missing = sorted(expected_tables - tables)
        unexpected = sorted(tables - expected_tables)
        raise RuntimeError(f"Unexpected schema: missing={missing}, unexpected={unexpected}")
    db.session.execute(text("SELECT 1"))

print("SQL smoke test passed")
