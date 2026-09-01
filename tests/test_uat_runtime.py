import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("missing", ["SECRET_KEY", "DATABASE_URL"])
def test_uat_config_requires_secret_environment_values(missing):
    environment = os.environ.copy()
    environment["SECRET_KEY"] = "isolated-test-secret"
    environment["DATABASE_URL"] = "sqlite:///:memory:"
    environment.pop(missing, None)

    completed = subprocess.run(
        [sys.executable, "-c", "from app import create_app; create_app('uat')"],
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode != 0
    assert f"{missing} environment variable is required" in completed.stderr
    assert "isolated-test-secret" not in completed.stderr


def test_uat_config_has_approved_runtime_behavior():
    environment = os.environ.copy()
    environment.update(
        {
            "SECRET_KEY": "isolated-test-secret",
            "DATABASE_URL": "sqlite:///:memory:",
            "MATERIAL_TAG_ISSUANCE_ENABLED": "1",
            "FINISHED_GOODS_MASTER_ENABLED": "1",
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from config import UATConfig; "
                "print(UATConfig.DEBUG, UATConfig.TESTING, UATConfig.MOCK_ERP_ENABLED, "
                "UATConfig.UAT_AUTO_LOGIN, UATConfig.UAT_AUTO_USERNAME, "
                "UATConfig.UAT_AUTO_STATION_CODE, "
                "UATConfig.MATERIAL_TAG_ISSUANCE_ENABLED, "
                "UATConfig.FINISHED_GOODS_MASTER_ENABLED)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.stdout.strip() == (
        "False False True True uat_admin UAT-ST01 True True"
    )


def test_healthz_is_unauthenticated_and_does_not_query_the_database():
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "uat",
            "SECRET_KEY": "isolated-test-secret",
            "DATABASE_URL": "sqlite:////dev/null/uat-health.db",
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from app import create_app; "
                "application = create_app('uat'); "
                "client = application.test_client(); "
                "response = client.get('/healthz'); "
                "assert response.status_code == 200; "
                "assert response.get_json() == {'status': 'ok'}; "
                "assert response.data == b'{\"status\":\"ok\"}\\n'; "
                "print('healthz-ok')"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.stdout.strip() == "healthz-ok"
    assert "isolated-test-secret" not in completed.stderr
