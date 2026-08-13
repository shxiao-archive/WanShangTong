import re

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import Notification, User, utc_now


ALLOWED_ACTIONS = {
    "open_onboarding_review",
    "open_onboarding_form",
    "open_service_application",
    "open_overview",
}


def safe_notification_text(value: str, limit: int) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit]


def add_notification(
    db: Session,
    *,
    recipient_user_id: int,
    notification_type: str,
    category: str,
    title: str,
    message: str,
    action: str,
    target_type: str,
    target_id: int | None,
    dedupe_key: str,
    is_demo: bool = False,
) -> Notification | None:
    if action not in ALLOWED_ACTIONS:
        raise ValueError("unsupported notification action")
    if any(
        isinstance(pending, Notification)
        and pending.recipient_user_id == recipient_user_id
        and pending.dedupe_key == dedupe_key
        for pending in db.new
    ):
        return None
    existing = db.scalar(
        select(Notification.id).where(
            Notification.recipient_user_id == recipient_user_id,
            Notification.dedupe_key == dedupe_key,
        )
    )
    if existing:
        return None
    row = Notification(
        recipient_user_id=recipient_user_id,
        type=notification_type,
        category=category,
        title=safe_notification_text(title, 120),
        message=safe_notification_text(message, 300),
        action=action,
        target_type=target_type,
        target_id=target_id,
        is_demo=is_demo,
        dedupe_key=dedupe_key[:180],
    )
    db.add(row)
    return row


def notify_active_operators(db: Session, **kwargs) -> None:
    operator_ids = db.scalars(
        select(User.id).where(User.role == "operator", User.is_active.is_(True))
    ).all()
    for operator_id in operator_ids:
        add_notification(db, recipient_user_id=operator_id, **kwargs)


def notify_merchant_account(db: Session, merchant_id: int, **kwargs) -> None:
    user_id = db.scalar(
        select(User.id).where(
            User.merchant_id == merchant_id,
            User.role == "merchant",
            User.is_active.is_(True),
        )
    )
    if user_id:
        add_notification(db, recipient_user_id=user_id, **kwargs)


def mark_related_notifications_read(
    db: Session,
    *,
    recipient_user_id: int,
    notification_type: str,
    target_type: str,
    target_id: int,
) -> None:
    db.execute(
        update(Notification)
        .where(
            Notification.recipient_user_id == recipient_user_id,
            Notification.type == notification_type,
            Notification.target_type == target_type,
            Notification.target_id == target_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=utc_now())
    )
