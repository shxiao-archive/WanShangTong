import hashlib
import hmac
import ipaddress
import re
import uuid
from datetime import date, datetime
from typing import Any

from fastapi import Request
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from .config import get_settings
from .models import AuditLog, User

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "current_password",
    "new_password",
    "invitation_code",
    "code_hash",
    "credential_encryption_key",
    "storage_key",
    "document_number",
    "authorization",
    "cookie",
    "set_cookie",
    "access_token",
    "refresh_token",
    "id_card_number",
    "identity_number",
}
MASKED_KEYS = {
    "phone",
    "contact_phone",
    "mobile",
    "telephone",
    "unified_social_credit_code",
}
PRIVATE_TEXT_KEYS = {
    "note",
    "merchant_note",
    "review_note",
    "message",
    "comment",
    "description_before",
    "description_after",
}
NAME_KEYS = {"contact_name", "legal_representative"}
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in SENSITIVE_KEYS or any(
        marker in normalized
        for marker in ("password", "token", "secret", "authorization", "cookie")
    )


def _is_private_text_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in PRIVATE_TEXT_KEYS or normalized.endswith(
        ("_note", "_message", "_comment")
    )


def safe_request_id(value: str | None) -> str:
    candidate = (value or "").strip()
    return candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else str(uuid.uuid4())


def request_client_ip(request: Request | None) -> str:
    if not request:
        return ""
    forwarded = [
        item.strip()
        for item in request.headers.get("x-forwarded-for", "").split(",")
        if item.strip()
    ]
    for candidate in reversed(forwarded):
        try:
            if ipaddress.ip_address(candidate).is_global:
                return candidate
        except ValueError:
            continue
    candidates = [request.headers.get("x-real-ip", "").strip()]
    if request.client:
        candidates.append(request.client.host)
    for candidate in candidates:
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return ""


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _masked_value(value: Any) -> str:
    text = str(value)
    if len(text) <= 5:
        return "***"
    return f"{text[:3]}***{text[-2:]}"


def _sanitize_value(value: Any, key: str = "") -> Any:
    normalized_key = key.lower()
    if _is_sensitive_key(normalized_key):
        return None
    if normalized_key in MASKED_KEYS and value is not None and value != "":
        return _masked_value(value)
    if _is_private_text_key(normalized_key) and value is not None and value != "":
        return "[REDACTED]"
    if normalized_key in NAME_KEYS and value is not None and value != "":
        text = str(value)
        return f"{text[:1]}**" if text else "***"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for child_key, child_value in value.items():
            if _is_sensitive_key(str(child_key)):
                continue
            result[str(child_key)] = _sanitize_value(child_value, str(child_key))
        return result
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(item) for item in value]
    return value


def sanitize(data: dict | None) -> dict | None:
    if data is None:
        return None
    return _sanitize_value(data)


def model_snapshot(model: Any) -> dict:
    return {
        column.key: _json_value(getattr(model, column.key))
        for column in inspect(model).mapper.column_attrs
    }


def add_audit(
    db: Session,
    actor: User | None,
    action: str,
    target_type: str,
    target_id: int | str,
    *,
    before: dict | None = None,
    after: dict | None = None,
    request: Request | None = None,
) -> None:
    client_ip = request_client_ip(request)
    ip_hash = (
        hmac.new(
            get_settings().jwt_secret.encode(),
            client_ip.encode(),
            hashlib.sha256,
        ).hexdigest()
        if client_ip
        else ""
    )
    db.add(
        AuditLog(
            actor_user_id=actor.id if actor else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            before_data=sanitize(before),
            after_data=sanitize(after),
            request_id=getattr(request.state, "request_id", "") if request else "",
            ip_hash=ip_hash,
        )
    )
