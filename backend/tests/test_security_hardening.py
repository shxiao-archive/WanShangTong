import re

import pytest
from pydantic import ValidationError

from app.audit import safe_request_id, sanitize
from app.config import Settings


def production_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "mysql_database": "wst2_test",
        "mysql_user": "wst2_test",
        "mysql_password": "database-password-for-isolated-tests",
        "jwt_secret": "jwt-secret-for-isolated-tests-0123456789",
        "credential_encryption_key": "credential-key-for-isolated-tests-0123456789",
        "cors_origins": "https://wst2.example.test",
        "demo_operator_password": "Operator-Test-Password-2026",
        "demo_merchant_password": "Merchant-Test-Password-2026",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_configuration_rejects_weak_defaults():
    production_settings()
    for override in (
        {"jwt_secret": "too-short"},
        {"credential_encryption_key": "too-short"},
        {"mysql_password": None},
        {"cors_origins": "*"},
        {"cors_origins": "http://wst2.example.test"},
        {
            "jwt_secret": "shared-secret-for-isolated-tests-0123456789",
            "credential_encryption_key": "shared-secret-for-isolated-tests-0123456789",
        },
        {"credential_encryption_previous_keys": "short-old-key"},
        {"demo_operator_password": "too-short"},
        {"demo_merchant_password": "too-short"},
        {
            "demo_operator_password": "Same-Test-Password-2026",
            "demo_merchant_password": "Same-Test-Password-2026",
        },
    ):
        with pytest.raises(ValidationError):
            production_settings(**override)


def test_audit_sanitizer_recursively_removes_secrets_and_private_text():
    clean = sanitize(
        {
            "username": "merchant-a",
            "contact_phone": "13812345678",
            "merchant_note": "call after 3pm",
            "nested": {
                "confirm_password": "NeverLogThis123",
                "Authorization": "Bearer secret",
                "refreshToken": "secret-token",
                "items": [{"operator_comment": "private"}],
            },
        }
    )
    assert clean["username"] == "merchant-a"
    assert clean["contact_phone"] == "138***78"
    assert clean["merchant_note"] == "[REDACTED]"
    assert "confirm_password" not in clean["nested"]
    assert "Authorization" not in clean["nested"]
    assert "refreshToken" not in clean["nested"]
    assert clean["nested"]["items"][0]["operator_comment"] == "[REDACTED]"


def test_request_id_rejects_control_characters_and_unbounded_input():
    assert safe_request_id("safe-request_01:part") == "safe-request_01:part"
    for unsafe in ("line1\nline2", "x" * 65, "包含中文", ""):
        generated = safe_request_id(unsafe)
        assert generated != unsafe
        assert re.fullmatch(r"[0-9a-f-]{36}", generated)
