import hashlib
from datetime import date
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook
from PIL import Image
from sqlalchemy import select
from starlette.requests import Request

from app.audit import request_client_ip
from app.agreements import PRIVACY_VERSION, RULES_VERSION
from app.database import SessionLocal
from app.config import get_settings
from app.main import app
from app.models import (
    CredentialDocument,
    MerchantOnboardingApplication,
    OperatorInvite,
)
from app.routers.auth import registration_attempts
from app.schemas import (
    USCC_CHARSET,
    USCC_WEIGHTS,
    normalize_and_validate_uscc,
    validate_uscc_subject_type,
    validate_password_strength,
)


def login(client: TestClient, username: str, password: str) -> dict:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def demo_login(client: TestClient, role: str) -> dict:
    settings = get_settings()
    password = (
        settings.demo_merchant_password
        if role == "merchant"
        else settings.demo_operator_password
    )
    return login(client, role, password)


def operator_headers(client: TestClient) -> dict:
    return auth_header(demo_login(client, "operator")["access_token"])


def agreement_acceptance() -> dict:
    return {
        "accepted_rules": True,
        "rules_version": RULES_VERSION,
        "accepted_privacy": True,
        "privacy_version": PRIVACY_VERSION,
    }


def valid_uscc(seed: str) -> str:
    digits = f"{sum(ord(char) for char in seed) % 100000:05d}"
    base = f"92500101MA5U{digits}"
    check_index = (31 - sum(
        USCC_CHARSET.index(char) * weight
        for char, weight in zip(base, USCC_WEIGHTS)
    ) % 31) % 31
    return base + USCC_CHARSET[check_index]


def test_uscc_normalization_accepts_whitespace_and_lowercase():
    code = valid_uscc("normalization")
    assert code.startswith("92")
    entered = f" {code[:6]}\n{code[6:12]}\t{code[12:].lower()} "
    assert normalize_and_validate_uscc(entered) == code


def test_uscc_subject_type_rejects_checksum_only_test_number():
    try:
        validate_uscc_subject_type("123456789012345678", "enterprise")
    except ValueError as exc:
        assert "应以91开头" in str(exc)
    else:
        raise AssertionError("checksum-only test number must not pass enterprise validation")


def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 16), "#16877e").save(output, format="PNG")
    return output.getvalue()


def submit_registered_application(
    client: TestClient,
    registration: dict,
    merchant: dict,
) -> int:
    token_headers = auth_header(registration["access_token"])
    code = merchant.get("unified_social_credit_code") or valid_uscc(merchant["name"])
    draft = {
        "subject_type": "individual_business",
        "legal_name": merchant.get("legal_name", f"{merchant['name']}经营部"),
        "unified_social_credit_code": code,
        "legal_representative": registration["user"]["display_name"],
        "registered_address": merchant["address"],
        "business_scope": "依法开展经营活动",
        "merchant_name": merchant["name"],
        "industry": merchant["industry"],
        "phone": merchant["phone"],
        "address": merchant["address"],
        "business_hours": merchant.get("business_hours", "09:00-21:00"),
        "contact_name": registration["user"]["display_name"],
        "contact_relationship": "business_operator",
        "authorization_confirmed": False,
        "scale": merchant.get("scale", "小微"),
        "employee_count": merchant.get("employee_count", 3),
        "store_area": merchant.get("store_area", 60),
        "network_environment": merchant.get("network_environment", "普通宽带"),
        "bandwidth_mbps": merchant.get("bandwidth_mbps", 100),
        "needs": merchant.get("needs", []),
        "retail_food_related": False,
        "retail_food_credential_type": None,
        "other_permit_required": False,
        "other_permit_name": "",
        "other_permit_number": "",
        "additional_permits": [],
        "current_step": 4,
    }
    saved = client.put(
        "/api/v1/merchant-onboarding/me/draft",
        headers=token_headers,
        json=draft,
    )
    assert saved.status_code == 200, saved.text
    uploads = ["business_license"]
    if merchant["industry"] == "餐饮":
        uploads.append("food_business_license")
    if merchant["industry"] == "住宿":
        uploads.append("accommodation_permit")
    for document_type in uploads:
        uploaded = client.post(
            "/api/v1/merchant-onboarding/me/documents",
            headers=token_headers,
            data={"document_type": document_type, "document_number": ""},
            files={"file": (f"{document_type}.png", png_bytes(), "image/png")},
        )
        assert uploaded.status_code == 201, uploaded.text
    submitted = client.post(
        "/api/v1/merchant-onboarding/me/submit",
        headers=token_headers,
        json={
            "truthfulness_confirmed": True,
            **agreement_acceptance(),
        },
    )
    assert submitted.status_code == 200, submitted.text
    return submitted.json()["data"]["id"]


def approve_registered_merchant(
    client: TestClient,
    registration: dict,
    merchant: dict,
) -> dict:
    token_headers = auth_header(registration["access_token"])
    application_id = submit_registered_application(client, registration, merchant)
    approved = client.patch(
        f"/api/v1/merchant-onboarding/{application_id}/review",
        headers=operator_headers(client),
        json={"action": "approve", "note": ""},
    )
    assert approved.status_code == 200, approved.text
    user = client.get("/api/v1/auth/me", headers=token_headers).json()["data"]
    return {**registration, "user": user}


def merchant_account(client: TestClient, merchant_id: int, username: str) -> dict:
    operator = operator_headers(client)
    users = client.get("/api/v1/users", headers=operator).json()["data"]
    existing = next((item for item in users if item["username"] == username), None)
    if existing:
        reset = client.post(f"/api/v1/users/{existing['id']}/reset-password", headers=operator)
        assert reset.status_code == 200
        temporary_password = reset.json()["data"]["temporary_password"]
        first = login(client, existing["username"], temporary_password)
        changed = client.post(
            "/api/v1/auth/change-password",
            headers=auth_header(first["access_token"]),
            json={"current_password": temporary_password, "new_password": "Valid2026Pass"},
        )
        assert changed.status_code == 200, changed.text
        assert client.get("/api/v1/auth/me", headers=auth_header(first["access_token"])).status_code == 401
        return changed.json()["data"]

    merchant = client.get(f"/api/v1/merchants/{merchant_id}", headers=operator).json()["data"]
    registration_attempts.clear()
    created = client.post(
        "/api/v1/auth/register",
        json={
            "account_type": "merchant",
            "username": username,
            "password": "Valid2026Pass",
            "display_name": "测试商户",
            "merchant_name": merchant["name"],
            "industry": merchant["industry"],
            "phone": merchant["phone"],
            "address": merchant["address"],
            **agreement_acceptance(),
        },
    )
    assert created.status_code == 201, created.text
    trial_merchant = {
        **merchant,
        "name": f"{merchant['name']}·{username}",
        "address": f"{merchant['address']}（测试门店）",
        "unified_social_credit_code": valid_uscc(username),
    }
    return approve_registered_merchant(
        client, created.json()["data"], trial_merchant
    )


def xlsx_bytes(rows: list[list]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["日期", "访客", "订单", "营业额", "评分", "到店", "外卖", "团购", "其他", "高峰小时"])
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_proxy_client_ip_uses_last_public_address():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [
                (b"x-forwarded-for", b"198.51.100.10, 8.8.8.8, 172.20.0.1"),
            ],
            "client": ("172.20.0.2", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )
    assert request_client_ip(request) == "8.8.8.8"


def test_password_rule_accepts_any_two_character_categories():
    assert validate_password_strength("lowercase123") == "lowercase123"
    assert validate_password_strength("UPPERCASE123") == "UPPERCASE123"
    assert validate_password_strength("Special#123") == "Special#123"
    assert validate_password_strength("username123") == "username123"
    assert validate_password_strength("letters#only") == "letters#only"
    assert validate_password_strength("1234567#") == "1234567#"
    for invalid in ("short1", "onlyletters", "12345678", "空白字符测试"):
        try:
            validate_password_strength(invalid)
        except ValueError:
            continue
        raise AssertionError(f"password should be rejected: {invalid}")


def test_health_logins_and_demo_scope():
    with TestClient(app) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/ready").status_code == 200
        merchant = demo_login(client, "merchant")
        operator = demo_login(client, "operator")
        assert merchant["user"]["merchant_id"] == 1
        assert operator["user"]["role"] == "operator"
        real = client.get("/api/v1/dashboard/overview", headers=auth_header(operator["access_token"])).json()["data"]
        demo = client.get("/api/v1/dashboard/overview?data_scope=demo", headers=auth_header(operator["access_token"])).json()["data"]
        assert real["merchant_count"] == 0
        assert demo["merchant_count"] == 6


def test_browser_session_uses_httponly_cookie_without_exposing_jwt():
    with TestClient(app) as client:
        browser_headers = {"X-WST2-Browser-Session": "1"}
        response = client.post(
            "/api/v1/auth/login",
            headers=browser_headers,
            json={
                "username": "operator",
                "password": get_settings().demo_operator_password,
            },
        )
        assert response.status_code == 200, response.text
        assert "access_token" not in response.json()["data"]
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "samesite=strict" in cookie
        assert "path=/api/v1" in cookie
        assert response.headers["cache-control"].startswith("no-store")

        assert client.get(
            "/api/v1/auth/me", headers=browser_headers
        ).status_code == 200
        # Cookies are deliberately ignored without the non-simple browser
        # session header, which provides the CSRF boundary.
        assert client.get("/api/v1/auth/me").status_code == 401
        assert client.post(
            "/api/v1/auth/logout", headers=browser_headers
        ).status_code == 200
        assert client.get(
            "/api/v1/auth/me", headers=browser_headers
        ).status_code == 401


def test_operator_cannot_submit_for_merchant_and_disabled_resource_is_hidden():
    with TestClient(app) as client:
        operator = operator_headers(client)
        merchant = demo_login(client, "merchant")
        merchant_headers = auth_header(merchant["access_token"])
        payload = {
            "merchant_id": 1,
            "resource_id": 1,
            "contact_name": "权限测试",
            "contact_phone": "13800000000",
            "merchant_note": "",
        }
        assert client.post(
            "/api/v1/service-applications", headers=operator, json=payload
        ).status_code == 403

        disabled = client.patch(
            "/api/v1/resources/1/status",
            headers=operator,
            json={"status": "disabled"},
        )
        assert disabled.status_code == 200, disabled.text
        try:
            merchant_resources = client.get(
                "/api/v1/resources", headers=merchant_headers
            )
            assert merchant_resources.status_code == 200
            assert 1 not in {item["id"] for item in merchant_resources.json()["data"]}
            assert client.post(
                "/api/v1/service-applications",
                headers=merchant_headers,
                json=payload,
            ).status_code == 404
        finally:
            enabled = client.patch(
                "/api/v1/resources/1/status",
                headers=operator,
                json={"status": "enabled"},
            )
            assert enabled.status_code == 200


def test_operator_can_list_legacy_onboarding_with_null_new_fields():
    registration_attempts.clear()
    with TestClient(app) as client:
        registration = client.post(
            "/api/v1/auth/register",
            json={
                "account_type": "merchant",
                "username": "legacy_onboarding",
                "password": "Legacy2026Pass",
                "display_name": "旧版申请人",
                **agreement_acceptance(),
            },
        )
        assert registration.status_code == 201, registration.text
        user_id = registration.json()["data"]["user"]["id"]
        merchant_headers = auth_header(
            registration.json()["data"]["access_token"]
        )
        assert client.put(
            "/api/v1/merchant-onboarding/me/draft",
            headers=merchant_headers,
            json={
                "merchant_name": "旧版待补充店铺",
                "phone": "13800000000",
                "address": "万州区旧版地址",
            },
        ).status_code == 200
        with SessionLocal() as db:
            application = db.scalar(
                select(MerchantOnboardingApplication).where(
                    MerchantOnboardingApplication.user_id == user_id
                )
            )
            for field_name in (
                "legal_name",
                "unified_social_credit_code",
                "legal_representative",
                "registered_address",
                "business_scope",
                "other_permit_name",
                "other_permit_number",
            ):
                setattr(application, field_name, None)
            application.status = "needs_changes"
            db.commit()

        response = client.get(
            "/api/v1/merchant-onboarding?status=all",
            headers=operator_headers(client),
        )
        assert response.status_code == 200, response.text
        item = next(
            row
            for row in response.json()["data"]["items"]
            if row["user_id"] == user_id
        )
        assert item["legal_name"] == ""
        assert item["other_permit_name"] == ""


def test_self_registration_invite_hash_and_single_use():
    registration_attempts.clear()
    with TestClient(app) as client:
        merchant = client.post(
            "/api/v1/auth/register",
            json={
                "account_type": "merchant",
                "username": "new_trial_shop",
                "password": "Secure2026Pass",
                "display_name": "试运营店主",
                "merchant_name": "测试新商户",
                "industry": "零售",
                "phone": "13800000001",
                "address": "万州区测试路 1 号",
                **agreement_acceptance(),
            },
        )
        assert merchant.status_code == 201, merchant.text
        merchant_data = merchant.json()["data"]
        assert merchant_data["user"]["role"] == "merchant"
        assert merchant_data["user"]["merchant_id"] is None
        assert merchant_data["user"]["must_change_password"] is False
        merchant_headers = auth_header(merchant_data["access_token"])
        assert client.get("/api/v1/resources", headers=merchant_headers).status_code == 403
        pending_id = submit_registered_application(
            client,
            merchant_data,
            {
                "name": "测试新商户",
                "industry": "零售",
                "phone": "13800000001",
                "address": "万州区测试路 1 号",
            },
        )

        operator = operator_headers(client)
        onboarding_summary = client.get(
            "/api/v1/merchant-onboarding/summary",
            headers=operator,
        )
        assert onboarding_summary.status_code == 200, onboarding_summary.text
        assert onboarding_summary.json()["data"]["pending_count"] >= 1
        assert pending_id in {
            item["id"]
            for item in onboarding_summary.json()["data"]["latest"]
        }
        assert client.get(
            "/api/v1/merchant-onboarding/summary",
            headers=merchant_headers,
        ).status_code == 403
        needs_changes = client.patch(
            f"/api/v1/merchant-onboarding/{pending_id}/review",
            headers=operator,
            json={"action": "request_changes", "note": "请核对经营地址"},
        )
        assert needs_changes.status_code == 200, needs_changes.text
        current = client.get(
            "/api/v1/merchant-onboarding/me", headers=merchant_headers
        ).json()["data"]
        assert current["status"] == "needs_changes"
        current["address"] = "万州区测试路 1 号附 1 号"
        saved = client.put(
            "/api/v1/merchant-onboarding/me/draft",
            headers=merchant_headers,
            json=current,
        )
        assert saved.status_code == 200, saved.text
        resubmitted = client.post(
            "/api/v1/merchant-onboarding/me/submit",
            headers=merchant_headers,
            json={
                "truthfulness_confirmed": True,
                **agreement_acceptance(),
            },
        )
        assert resubmitted.status_code == 200, resubmitted.text
        approved = client.patch(
            f"/api/v1/merchant-onboarding/{pending_id}/review",
            headers=operator,
            json={"action": "approve", "note": ""},
        )
        assert approved.status_code == 200, approved.text
        assert client.get("/api/v1/auth/me", headers=merchant_headers).json()["data"]["merchant_id"] is not None
        generated = client.post("/api/v1/auth/operator-invites", headers=operator)
        assert generated.status_code == 201, generated.text
        invitation_code = generated.json()["data"]["invitation_code"]
        with SessionLocal() as db:
            stored = db.scalar(select(OperatorInvite).order_by(OperatorInvite.id.desc()))
            assert stored.code_hash != invitation_code
        assert stored.code_hash == hashlib.sha256(invitation_code.encode()).hexdigest()

        manager = client.post(
            "/api/v1/auth/register",
            json={
                "account_type": "operator",
                "username": "new_manager",
                "password": "Manager2026Pass",
                "display_name": "新管理人员",
                "invitation_code": invitation_code,
                **agreement_acceptance(),
            },
        )
        assert manager.status_code == 201, manager.text
        assert manager.json()["data"]["user"]["role"] == "operator"
        replay = client.post(
            "/api/v1/auth/register",
            json={
                "account_type": "operator",
                "username": "replay_manager",
                "password": "Manager2027Pass",
                "display_name": "重复使用",
                "invitation_code": invitation_code,
                **agreement_acceptance(),
            },
        )
        assert replay.status_code == 422


def test_resource_subscription_count_uses_completed_real_merchants():
    registration_attempts.clear()
    with TestClient(app) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "account_type": "merchant",
                "username": "subscription_shop",
                "password": "Subscribe2026Pass",
                "display_name": "订阅测试店主",
                "merchant_name": "订阅统计测试商户",
                "industry": "餐饮",
                "phone": "13800000002",
                "address": "万州区订阅测试路 2 号",
                **agreement_acceptance(),
            },
        )
        assert registered.status_code == 201, registered.text
        merchant_data = registered.json()["data"]
        merchant_data = approve_registered_merchant(
            client,
            merchant_data,
            {
                "name": "订阅统计测试商户",
                "industry": "餐饮",
                "phone": "13800000002",
                "address": "万州区订阅测试路 2 号",
            },
        )
        merchant_headers = auth_header(merchant_data["access_token"])
        merchant_id = merchant_data["user"]["merchant_id"]
        created = client.post(
            "/api/v1/service-applications",
            headers=merchant_headers,
            json={
                "merchant_id": merchant_id,
                "resource_id": 1,
                "contact_name": "订阅测试店主",
                "contact_phone": "13800000002",
                "merchant_note": "",
            },
        )
        assert created.status_code == 201, created.text
        application_id = created.json()["data"]["id"]
        operator = operator_headers(client)
        for next_status in ("processing", "completed"):
            changed = client.patch(
                f"/api/v1/service-applications/{application_id}/status",
                headers=operator,
                json={"status": next_status, "note": ""},
            )
            assert changed.status_code == 200, changed.text
        operator_resources = client.get("/api/v1/resources", headers=operator).json()["data"]
        resource = next(item for item in operator_resources if item["id"] == 1)
        assert resource["subscription_count"] == 1
        merchant_resources = client.get(
            "/api/v1/resources",
            headers=merchant_headers,
        ).json()["data"]
        merchant_resource = next(item for item in merchant_resources if item["id"] == 1)
        assert merchant_resource["subscription_count"] == 0


def test_onboarding_credential_is_private_encrypted_and_deletable():
    registration_attempts.clear()
    with TestClient(app) as client:
        owner = client.post(
            "/api/v1/auth/register",
            json={
                "account_type": "merchant",
                "username": "credential_owner",
                "password": "Credential2026",
                "display_name": "资质申请人",
                **agreement_acceptance(),
            },
        ).json()["data"]
        owner_headers = auth_header(owner["access_token"])
        invalid = client.post(
            "/api/v1/merchant-onboarding/me/documents",
            headers=owner_headers,
            data={"document_type": "business_license"},
            files={"file": ("broken.png", b"not-an-image", "image/png")},
        )
        assert invalid.status_code == 415
        uploaded = client.post(
            "/api/v1/merchant-onboarding/me/documents",
            headers=owner_headers,
            data={"document_type": "business_license"},
            files={"file": ("license.png", png_bytes(), "image/png")},
        )
        assert uploaded.status_code == 201, uploaded.text
        document_id = uploaded.json()["data"]["id"]
        with SessionLocal() as db:
            document = db.get(CredentialDocument, document_id)
            encrypted = (
                Path(get_settings().upload_dir) / document.storage_key
            ).read_bytes()
            assert not encrypted.startswith(b"\x89PNG")
            assert not encrypted.startswith(b"\xff\xd8")

        assert client.get(
            f"/api/v1/credential-documents/{document_id}/content"
        ).status_code == 401
        registration_attempts.clear()
        other = client.post(
            "/api/v1/auth/register",
            json={
                "account_type": "merchant",
                "username": "credential_other",
                "password": "Credential2027",
                "display_name": "其他申请人",
                **agreement_acceptance(),
            },
        ).json()["data"]
        assert client.get(
            f"/api/v1/credential-documents/{document_id}/content",
            headers=auth_header(other["access_token"]),
        ).status_code == 403
        content = client.get(
            f"/api/v1/credential-documents/{document_id}/content",
            headers=owner_headers,
        )
        assert content.status_code == 200
        assert content.headers["cache-control"].startswith("no-store")
        assert client.delete(
            f"/api/v1/credential-documents/{document_id}",
            headers=owner_headers,
        ).status_code == 200
        assert client.get(
            f"/api/v1/credential-documents/{document_id}/content",
            headers=owner_headers,
        ).status_code == 404


def test_account_reset_and_cross_merchant_isolation():
    with TestClient(app) as client:
        account = merchant_account(client, 2, "merchant_two")
        token = account["access_token"]
        merchant_id = account["user"]["merchant_id"]
        assert account["user"]["must_change_password"] is False
        merchant = client.get(f"/api/v1/merchants/{merchant_id}", headers=auth_header(token))
        assert merchant.status_code == 200
        merchant_payload = merchant.json()["data"]
        merchant_payload.update(
            {
                "scale": "中小",
                "employee_count": 12,
                "store_area": 220,
            }
        )
        updated = client.put(
            f"/api/v1/merchants/{merchant_id}",
            headers=auth_header(token),
            json=merchant_payload,
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["data"]["scale"] == "中小"
        assert updated.json()["data"]["employee_count"] == 12
        assert updated.json()["data"]["store_area"] == 220
        assert client.get("/api/v1/merchants/1", headers=auth_header(token)).status_code == 403
        reset = client.post(
            f"/api/v1/users/{account['user']['id']}/reset-password",
            headers=operator_headers(client),
        )
        assert reset.status_code == 200
        assert client.get("/api/v1/auth/me", headers=auth_header(token)).status_code == 401


def test_operator_merchant_pages_are_read_only():
    with TestClient(app) as client:
        headers = operator_headers(client)
        merchant = client.get("/api/v1/merchants/1", headers=headers)
        assert merchant.status_code == 200
        assert client.put(
            "/api/v1/merchants/1",
            headers=headers,
            json=merchant.json()["data"],
        ).status_code == 403
        assert client.post(
            "/api/v1/merchants",
            headers=headers,
            json=merchant.json()["data"],
        ).status_code == 405

        business_rows = client.get(
            "/api/v1/merchants/1/business-data?days=30",
            headers=headers,
        )
        assert business_rows.status_code == 200
        payload = {
            "business_date": "2020-04-01",
            "visitors": 10,
            "orders": 4,
            "revenue": 100,
            "rating": 4.8,
            "dine_in_orders": 2,
            "delivery_orders": 1,
            "group_buy_orders": 1,
            "other_orders": 0,
            "peak_hour": 12,
        }
        assert client.post(
            "/api/v1/merchants/1/business-data",
            headers=headers,
            json=payload,
        ).status_code == 403
        assert client.get(
            "/api/v1/merchants/1/business-data/template",
            headers=headers,
        ).status_code == 403
        assert client.get(
            "/api/v1/merchants/1/business-data/export",
            headers=headers,
        ).status_code == 200


def test_account_lock_after_five_failures():
    with TestClient(app) as client:
        operator = operator_headers(client)
        users = client.get("/api/v1/users", headers=operator).json()["data"]
        account = next((item for item in users if item["merchant_id"] == 3), None)
        if not account:
            merchant = client.get("/api/v1/merchants/3", headers=operator).json()["data"]
            registration_attempts.clear()
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "account_type": "merchant",
                    "username": "lock_test",
                    "password": "Lock2026Pass",
                    "display_name": "锁定测试",
                    "merchant_name": merchant["name"],
                    "industry": merchant["industry"],
                    "phone": merchant["phone"],
                    "address": merchant["address"],
                    **agreement_acceptance(),
                },
            )
            assert response.status_code == 201, response.text
            approve_registered_merchant(client, response.json()["data"], merchant)
            correct_password = "Lock2026Pass"
        else:
            response = client.post(f"/api/v1/users/{account['id']}/reset-password", headers=operator)
            correct_password = response.json()["data"]["temporary_password"]
        for _ in range(5):
            assert client.post("/api/v1/auth/login", json={"username": "lock_test", "password": "Wrong#2026"}).status_code == 401
        assert client.post("/api/v1/auth/login", json={"username": "lock_test", "password": correct_password}).status_code == 423


def test_private_media_requires_owner_and_is_deleted_with_product():
    image_output = BytesIO()
    Image.new("RGB", (8, 8), "#16877e").save(image_output, format="PNG")
    png = image_output.getvalue()
    with TestClient(app) as client:
        merchant = demo_login(client, "merchant")
        headers = auth_header(merchant["access_token"])
        invalid = client.post(
            "/api/v1/merchants/1/product-images",
            headers=headers,
            files={"image": ("broken.png", b"not-a-real-image", "image/png")},
        )
        assert invalid.status_code == 415
        uploaded = client.post(
            "/api/v1/merchants/1/product-images",
            headers=headers,
            files={"image": ("product.png", png, "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        media_id = uploaded.json()["data"]["id"]
        assert client.get(f"/api/v1/media/{media_id}/content").status_code == 401
        assert client.get(f"/api/v1/media/{media_id}/content", headers=headers).status_code == 200
        other = merchant_account(client, 4, "media_other")
        assert client.get(
            f"/api/v1/media/{media_id}/content",
            headers=auth_header(other["access_token"]),
        ).status_code == 403
        assert client.delete(f"/api/v1/media/{media_id}", headers=headers).status_code == 200
        assert client.get(f"/api/v1/media/{media_id}/content", headers=headers).status_code == 404


def test_application_duplicate_transitions_notes_and_merchant_cancel():
    with TestClient(app) as client:
        merchant = demo_login(client, "merchant")
        merchant_headers = auth_header(merchant["access_token"])
        payload = {
            "merchant_id": 1,
            "resource_id": 1,
            "contact_name": "陈店长",
            "contact_phone": "023-5858-1024",
            "merchant_note": "下午联系",
        }
        created = client.post("/api/v1/service-applications", headers=merchant_headers, json=payload)
        assert created.status_code == 201, created.text
        application_id = created.json()["data"]["id"]
        duplicate = client.post("/api/v1/service-applications", headers=merchant_headers, json=payload)
        assert duplicate.status_code == 409
        assert duplicate.json()["data"]["application_id"] == application_id
        merchant_note = client.post(
            f"/api/v1/service-applications/{application_id}/notes",
            headers=merchant_headers,
            json={"note": "请在下午三点后联系"},
        )
        assert merchant_note.status_code == 200, merchant_note.text
        assert merchant_note.json()["data"]["events"][-1]["event_type"] == "merchant_note"
        other_merchant = merchant_account(client, 4, "application_note_other")
        assert client.post(
            f"/api/v1/service-applications/{application_id}/notes",
            headers=auth_header(other_merchant["access_token"]),
            json={"note": "不应写入其他商户申请"},
        ).status_code == 403
        operator = operator_headers(client)
        assert client.post(
            f"/api/v1/service-applications/{application_id}/notes",
            headers=operator,
            json={"note": "已安排联系"},
        ).status_code == 200
        assert client.patch(
            f"/api/v1/service-applications/{application_id}/status",
            headers=operator,
            json={"status": "contacted", "note": ""},
        ).status_code == 422
        for next_status in ("processing", "completed"):
            response = client.patch(
                f"/api/v1/service-applications/{application_id}/status",
                headers=operator,
                json={"status": next_status, "note": next_status},
            )
            assert response.status_code == 200, response.text
        assert client.post(
            f"/api/v1/service-applications/{application_id}/notes",
            headers=merchant_headers,
            json={"note": "已结束后不应继续留言"},
        ).status_code == 422
        again = client.post("/api/v1/service-applications", headers=merchant_headers, json=payload)
        assert again.status_code == 201
        second_id = again.json()["data"]["id"]
        canceled = client.patch(
            f"/api/v1/service-applications/{second_id}/status",
            headers=merchant_headers,
            json={"status": "canceled", "note": "暂不需要"},
        )
        assert canceled.status_code == 200


def test_business_data_validation_soft_delete_and_excel_transaction():
    with TestClient(app) as client:
        headers = auth_header(demo_login(client, "merchant")["access_token"])
        invalid = {
            "business_date": "2020-02-01", "visitors": 10, "orders": 2, "revenue": 10,
            "rating": 5, "dine_in_orders": 2, "delivery_orders": 2,
            "group_buy_orders": 0, "other_orders": 0, "peak_hour": 12,
        }
        assert client.post("/api/v1/merchants/1/business-data", headers=headers, json=invalid).status_code == 422
        valid = {**invalid, "orders": 4}
        created = client.post("/api/v1/merchants/1/business-data", headers=headers, json=valid)
        assert created.status_code in {201, 409}
        if created.status_code == 201:
            data_id = created.json()["data"]["id"]
            assert client.delete(f"/api/v1/merchants/1/business-data/{data_id}", headers=headers).status_code == 200
        content = xlsx_bytes([
            ["2020-03-01", 10, 4, 100.25, 4.8, 2, 1, 1, 0, 12],
            ["2020-03-02", 10, 5, 80, 4.7, 2, 1, 1, 0, 13],
        ])
        preview = client.post(
            "/api/v1/merchants/1/business-data/import?dry_run=true",
            headers=headers,
            files={"file": ("data.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert preview.status_code == 200
        assert preview.json()["data"]["error_count"] == 1
        commit = client.post(
            "/api/v1/merchants/1/business-data/import?dry_run=false",
            headers=headers,
            files={"file": ("data.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert commit.status_code == 422
        rows = client.get("/api/v1/merchants/1/business-data?date_from=2020-03-01&date_to=2020-03-02", headers=headers).json()["data"]
        assert rows == []
        template = client.get("/api/v1/merchants/1/business-data/template", headers=headers)
        exported = client.get("/api/v1/merchants/1/business-data/export", headers=headers)
        assert template.status_code == exported.status_code == 200
        assert template.headers["content-type"].startswith("application/vnd.openxmlformats")
