from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db

application = create_app("development")
with application.app_context():
    tables = inspect(db.engine).get_table_names()
    if len(tables) != 15 or "alembic_version" not in tables:
        raise RuntimeError(f"Unexpected schema: {tables}")
    db.session.execute(text("SELECT 1"))

print("SQL smoke test passed")
