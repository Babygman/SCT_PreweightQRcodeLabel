import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def environment_bool(name, default=False):
    """Read a fail-closed boolean from the process environment."""
    value = os.environ.get(name)
    if value is None:
        return bool(default)

    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"", "0", "false", "no", "off"}:
        return False
    return False


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
    MATERIAL_TAG_ISSUANCE_ENABLED = environment_bool(
        "MATERIAL_TAG_ISSUANCE_ENABLED"
    )
    MATERIAL_IMPORT_MAX_BYTES = 5 * 1024 * 1024
    MATERIAL_IMPORT_MAX_ROWS = 5_000
    MATERIAL_IMPORT_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
    MATERIAL_TAG_DRAFT_LIFETIME_MINUTES = 60
    MATERIAL_TAG_SEARCH_PAGE_SIZE = 25
    MATERIAL_TAG_HISTORY_PAGE_SIZE = 25
    MATERIAL_TAG_LABEL_WIDTH_IN = 3.0
    MATERIAL_TAG_LABEL_HEIGHT_IN = 2.5
    MATERIAL_TAG_LABEL_OFFSET_TOP_IN = 0.0
    MATERIAL_TAG_LABEL_OFFSET_LEFT_IN = 0.0
    MATERIAL_TAG_LABEL_PADDING_IN = 0.08
    MATERIAL_TAG_LABEL_QR_IN = 1.05
    MATERIAL_TAG_LABEL_FONT_SCALE = 1.0
    MATERIAL_TAG_LABEL_LINE_SPACING = 1.05

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
    MATERIAL_TAG_ISSUANCE_ENABLED = False


CONFIGS = {
    "development": DevelopmentConfig,
    "production": Config,
    "testing": TestingConfig,
}
