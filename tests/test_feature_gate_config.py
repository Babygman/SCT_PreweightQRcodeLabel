import os
import subprocess
import sys

import pytest

from app import create_app
from config import environment_bool


@pytest.mark.parametrize("value", ["1", "true", "TRUE", " yes ", "On"])
def test_environment_bool_accepts_only_explicit_true_values(monkeypatch, value):
    monkeypatch.setenv("TEST_BOOLEAN_FLAG", value)

    result = environment_bool("TEST_BOOLEAN_FLAG")

    assert result is True
    assert isinstance(result, bool)


@pytest.mark.parametrize(
    "value", ["", " ", "0", "false", "FALSE", " no ", "Off", "invalid", "2"]
)
def test_environment_bool_is_false_for_false_or_invalid_values(monkeypatch, value):
    monkeypatch.setenv("TEST_BOOLEAN_FLAG", value)

    result = environment_bool("TEST_BOOLEAN_FLAG", default=True)

    assert result is False
    assert isinstance(result, bool)


def test_environment_bool_uses_boolean_default_when_missing(monkeypatch):
    monkeypatch.delenv("TEST_BOOLEAN_FLAG", raising=False)

    assert environment_bool("TEST_BOOLEAN_FLAG") is False
    assert environment_bool("TEST_BOOLEAN_FLAG", default=True) is True


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "False False False"), ("1", "True True False"), ("invalid", "False False False")],
)
def test_feature_gate_configuration_is_resolved_at_import_time(value, expected):
    environment = os.environ.copy()
    if value is None:
        environment.pop("MATERIAL_TAG_ISSUANCE_ENABLED", None)
    else:
        environment["MATERIAL_TAG_ISSUANCE_ENABLED"] = value

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from config import Config, DevelopmentConfig, TestingConfig; "
                "print(Config.MATERIAL_TAG_ISSUANCE_ENABLED, "
                "DevelopmentConfig.MATERIAL_TAG_ISSUANCE_ENABLED, "
                "TestingConfig.MATERIAL_TAG_ISSUANCE_ENABLED)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.stdout.strip() == expected


def test_direct_flask_config_override_still_controls_the_feature():
    application = create_app("testing")
    assert application.config["MATERIAL_TAG_ISSUANCE_ENABLED"] is False

    application.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True

    assert application.config["MATERIAL_TAG_ISSUANCE_ENABLED"] is True
