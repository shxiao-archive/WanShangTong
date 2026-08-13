from fastapi.testclient import TestClient

from app.agreements import PRIVACY_VERSION, RULES_VERSION
from app.config import get_settings
from app.main import app
from app.routers.auth import attempts, registration_attempts


def test_login_is_restricted_to_matching_portal():
    settings = get_settings()
    attempts.clear()
    with TestClient(app) as client:
        wrong_portal = client.post(
            "/api/v1/auth/login",
            headers={"X-WST2-Portal": "operator"},
            json={
                "username": "merchant",
                "password": settings.demo_merchant_password,
            },
        )
        assert wrong_portal.status_code == 403
        assert wrong_portal.json()["message"] == "该账号请前往商户端登录"

        correct_portal = client.post(
            "/api/v1/auth/login",
            headers={
                "X-WST2-Browser-Session": "1",
                "X-WST2-Portal": "merchant",
            },
            json={
                "username": "merchant",
                "password": settings.demo_merchant_password,
            },
        )
        assert correct_portal.status_code == 200
        assert "access_token" not in correct_portal.json()["data"]

        cross_portal_session = client.get(
            "/api/v1/auth/me",
            headers={
                "X-WST2-Browser-Session": "1",
                "X-WST2-Portal": "operator",
            },
        )
        assert cross_portal_session.status_code == 403


def test_registration_is_restricted_to_matching_portal():
    registration_attempts.clear()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            headers={"X-WST2-Portal": "merchant"},
            json={
                "account_type": "operator",
                "username": "wrong_portal_operator",
                "password": "PortalTest2026",
                "display_name": "入口隔离测试",
                "invitation_code": "not-consumed-because-portal-is-wrong",
                "accepted_rules": True,
                "rules_version": RULES_VERSION,
                "accepted_privacy": True,
                "privacy_version": PRIVACY_VERSION,
            },
        )
        assert response.status_code == 403
        assert response.json()["message"] == "该账号请前往管理端登录"
