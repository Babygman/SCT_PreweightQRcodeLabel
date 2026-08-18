import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Bangkok")
    UAT_AUTO_LOGIN = False
    # Stage A/B tables may not exist in an environment until the approved
    # deployment migration has been applied. Keep the feature unavailable by
    # default so disabled routes never query those tables.
    MATERIAL_TAG_ISSUANCE_ENABLED = False
    MATERIAL_IMPORT_MAX_BYTES = 5 * 1024 * 1024
    MATERIAL_IMPORT_MAX_ROWS = 5_000
    MATERIAL_IMPORT_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
    MATERIAL_TAG_DRAFT_LIFETIME_MINUTES = 60
    MATERIAL_TAG_SEARCH_PAGE_SIZE = 25

    @classmethod
    def validate(cls):
        if not cls.SECRET_KEY:
            raise RuntimeError("SECRET_KEY environment variable is required")
        if not cls.SQLALCHEMY_DATABASE_URI:
            raise RuntimeError("DATABASE_URL environment variable is required")


class DevelopmentConfig(Config):
    SECRET_KEY = os.environ.get("SECRET_KEY", "development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'app.db'}"
    )
    DEBUG = True
    MOCK_ERP_ENABLED = True
    UAT_AUTO_LOGIN = True
    UAT_AUTO_USERNAME = "uat_admin"
    UAT_AUTO_STATION_CODE = "UAT-ST01"


class TestingConfig(Config):
    SECRET_KEY = "test-only-secret"
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    MOCK_ERP_ENABLED = True


CONFIGS = {
    "development": DevelopmentConfig,
    "production": Config,
    "testing": TestingConfig,
}
