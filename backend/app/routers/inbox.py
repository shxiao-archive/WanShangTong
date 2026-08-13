from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import password_ready_user
from ..models import (
    Merchant,
    MerchantOnboardingApplication,
    Notification,
    ServiceApplication,
    User,
    utc_now,
)
from ..schemas import Envelope, NotificationOut, WorkItemOut

router = APIRouter(prefix="/inbox", tags=["通知与待办"])


def notification_data(row: Notification) -> NotificationOut:
    return NotificationOut.model_validate(row)


def notification_conditions(user: User, state: str, category: str, period: str):
    conditions = [Notification.recipient_user_id == user.id]
    if state == "unread":
        conditions.append(Notification.read_at.is_(None))
    if category != "all":
        conditions.append(Notification.category == category)
    if period != "all":
        days = 7 if period == "7d" else 30
        conditions.append(Notification.created_at >= utc_now() - timedelta(days=days))
    return conditions


def inbox_counts(db: Session, user: User) -> dict:
    unread_count = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.recipient_user_id == user.id,
            Notification.read_at.is_(None),
        )
    ) or 0
    latest_notification_id = db.scalar(
        select(func.max(Notification.id)).where(
            Notification.recipient_user_id == user.id
        )
    ) or 0
    onboarding_pending_count = 0
    onboarding_needs_changes_count = 0
    service_pending_count = 0
    service_processing_count = 0
    todo_count = 0
    if user.role == "operator":
        onboarding_pending_count = db.scalar(
            select(func.count())
            .select_from(MerchantOnboardingApplication)
            .where(MerchantOnboardingApplication.status == "pending")
        ) or 0
        service_counts = dict(
            db.execute(
                select(ServiceApplication.status, func.count())
                .where(ServiceApplication.status.in_(("pending", "processing")))
                .group_by(ServiceApplication.status)
            ).all()
        )
        service_pending_count = service_counts.get("pending", 0)
        service_processing_count = service_counts.get("processing", 0)
        todo_count = (
            onboarding_pending_count
            + service_pending_count
            + service_processing_count
        )
    return {
        "unread_count": unread_count,
        "latest_notification_id": latest_notification_id,
        "todo_count": todo_count,
        "onboarding_pending_count": onboarding_pending_count,
        "service_pending_count": service_pending_count,
        "service_processing_count": service_processing_count,
        "onboarding_needs_changes_count": onboarding_needs_changes_count,
    }


@router.get("/summary")
def summary(
    db: Session = Depends(get_db), user: User = Depends(password_ready_user)
):
    return Envelope(data=inbox_counts(db, user))


@router.get("/notifications")
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    state: str = Query("all", pattern="^(all|unread)$"),
    category: str = Query("all", pattern="^(all|onboarding|service)$"),
    period: str = Query("7d", pattern="^(7d|30d|all)$"),
    after_id: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(password_ready_user),
):
    effective_period = period if user.role == "operator" else "all"
    conditions = notification_conditions(user, state, category, effective_period)
    if after_id is not None:
        conditions.append(Notification.id > after_id)
    total = db.scalar(
        select(func.count()).select_from(Notification).where(*conditions)
    ) or 0
    statement = select(Notification).where(*conditions)
    if after_id is not None:
        statement = statement.order_by(Notification.id).limit(page_size)
        page = 1
    else:
        statement = (
            statement.order_by(
                Notification.read_at.is_not(None),
                Notification.created_at.desc(),
                Notification.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    rows = db.scalars(statement).all()
    return Envelope(
        data={
            "items": [notification_data(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.patch("/notifications/{notification_id}/read")
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(password_ready_user),
):
    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_user_id == user.id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="通知不存在")
    conditions = [
        Notification.recipient_user_id == user.id,
        Notification.read_at.is_(None),
    ]
    if row.target_id is None:
        conditions.append(Notification.id == row.id)
    else:
        conditions.extend(
            (
                Notification.target_type == row.target_type,
                Notification.target_id == row.target_id,
            )
        )
    db.execute(update(Notification).where(*conditions).values(read_at=utc_now()))
    db.commit()
    db.refresh(row)
    return Envelope(message="同一申请的通知已全部标记为已读", data=notification_data(row))


@router.post("/notifications/read-all")
def read_all_notifications(
    db: Session = Depends(get_db), user: User = Depends(password_ready_user)
):
    result = db.execute(
        update(Notification)
        .where(
            Notification.recipient_user_id == user.id,
            Notification.read_at.is_(None),
        )
        .values(read_at=utc_now())
    )
    db.commit()
    return Envelope(message="全部通知已读", data={"updated_count": result.rowcount or 0})


def operator_work_items(db: Session, category: str) -> list[WorkItemOut]:
    items: list[WorkItemOut] = []
    if category in {"all", "onboarding"}:
        rows = db.execute(
            select(MerchantOnboardingApplication, User)
            .join(User, User.id == MerchantOnboardingApplication.user_id)
            .where(MerchantOnboardingApplication.status == "pending")
        ).all()
        for row, applicant in rows:
            items.append(
                WorkItemOut(
                    key=f"onboarding:{row.id}",
                    category="onboarding",
                    title=row.merchant_name,
                    summary=f"{applicant.display_name}提交的入驻申请",
                    status="pending",
                    status_label="待审核",
                    is_demo=False,
                    created_at=row.submitted_at or row.created_at,
                    updated_at=row.updated_at,
                    action="open_onboarding_review",
                    target_id=row.id,
                )
            )
    if category in {"all", "service"}:
        rows = db.execute(
            select(ServiceApplication, Merchant.name)
            .join(Merchant, Merchant.id == ServiceApplication.merchant_id)
            .where(ServiceApplication.status.in_(("pending", "processing")))
        ).all()
        for row, merchant_name in rows:
            resource_name = str((row.resource_snapshot or {}).get("name") or "服务申请")
            items.append(
                WorkItemOut(
                    key=f"service:{row.id}",
                    category="service",
                    title=resource_name,
                    summary=f"{merchant_name}提交的服务申请",
                    status=row.status,
                    status_label="待受理" if row.status == "pending" else "办理中",
                    is_demo=row.is_demo,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    action="open_service_application",
                    target_id=row.id,
                )
            )
    return items


@router.get("/work-items")
def list_work_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str = Query("all", pattern="^(all|onboarding|service)$"),
    db: Session = Depends(get_db),
    user: User = Depends(password_ready_user),
):
    items = operator_work_items(db, category) if user.role == "operator" else []
    priority = {"pending": 0, "needs_changes": 0, "processing": 1}
    items.sort(key=lambda item: (priority.get(item.status, 2), item.created_at, item.key))
    total = len(items)
    start = (page - 1) * page_size
    return Envelope(
        data={
            "items": items[start : start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )
