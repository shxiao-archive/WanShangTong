from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..audit import add_audit, model_snapshot
from ..database import get_db
from ..deps import assert_merchant_access, current_user
from ..models import (
    ApplicationEvent,
    Merchant,
    ServiceApplication,
    ServiceResource,
    User,
    utc_now,
)
from ..notifications import notify_active_operators, notify_merchant_account
from ..rules import recommend
from ..schemas import (
    ApplicationCreate,
    ApplicationNoteIn,
    ApplicationOut,
    ApplicationStatusIn,
    Envelope,
)

router = APIRouter(prefix="/service-applications", tags=["服务申请"])
ACTIVE_STATUSES = {"pending", "processing"}
TRANSITIONS = {
    "pending": {"processing", "canceled"},
    "processing": {"completed", "canceled"},
    "completed": set(),
    "canceled": set(),
}


def application_query():
    return select(ServiceApplication).options(selectinload(ServiceApplication.events))


def require_application(db: Session, application_id: int) -> ServiceApplication:
    row = db.scalar(application_query().where(ServiceApplication.id == application_id))
    if not row:
        raise HTTPException(status_code=404, detail="服务申请不存在")
    return row


def application_data(row: ServiceApplication, merchant_name: str | None = None) -> dict:
    data = ApplicationOut.model_validate(row).model_dump()
    if merchant_name is not None:
        data["merchant_name"] = merchant_name
    return data


@router.post("", status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if user.role != "merchant" or user.merchant_id != payload.merchant_id:
        raise HTTPException(status_code=403, detail="仅商户可以为本店提交服务申请")
    merchant = db.get(Merchant, payload.merchant_id)
    resource = db.get(ServiceResource, payload.resource_id)
    if not merchant:
        raise HTTPException(status_code=404, detail="商户不存在")
    if not resource or resource.status != "enabled":
        raise HTTPException(status_code=404, detail="推荐资源不存在或已停用")
    active_key = f"{payload.merchant_id}:{payload.resource_id}"
    existing = db.scalar(
        application_query().where(ServiceApplication.active_key == active_key)
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"message": "已有进行中的申请", "data": {"application_id": existing.id}},
        )
    recommendation = next(
        (
            item
            for item in recommend(
                merchant,
                db.scalars(
                    select(ServiceResource).where(ServiceResource.status == "enabled")
                ).all(),
            )
            if item["id"] == resource.id
        ),
        None,
    )
    snapshot = {
        "name": resource.name,
        "category": resource.category,
        "description": resource.description,
        "price": resource.price,
        "unit": resource.unit,
        "included_services": resource.included_services,
    }
    row = ServiceApplication(
        merchant_id=merchant.id,
        resource_id=resource.id,
        created_by=user.id,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        merchant_note=payload.merchant_note,
        recommendation_score=recommendation["score"] if recommendation else 0,
        recommendation_reasons=recommendation["reasons"] if recommendation else [],
        resource_snapshot=snapshot,
        status="pending",
        active_key=active_key,
        is_demo=merchant.is_demo,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        existing_id = db.scalar(
            select(ServiceApplication.id).where(ServiceApplication.active_key == active_key)
        )
        raise HTTPException(
            status_code=409,
            detail={"message": "已有进行中的申请", "data": {"application_id": existing_id}},
        ) from exc
    db.add(
        ApplicationEvent(
            application_id=row.id,
            actor_user_id=user.id,
            event_type="created",
            to_status="pending",
            note=payload.merchant_note,
        )
    )
    notify_active_operators(
        db,
        notification_type="service_application_created",
        category="service",
        title="新的服务申请",
        message=f"{merchant.name}申请了{snapshot['name']}，请及时处理",
        action="open_service_application",
        target_type="service_application",
        target_id=row.id,
        dedupe_key=f"service_application:{row.id}:created",
        is_demo=row.is_demo,
    )
    add_audit(
        db,
        user,
        "application.created",
        "service_application",
        row.id,
        after=model_snapshot(row),
        request=request,
    )
    db.commit()
    return Envelope(
        message="服务申请已提交",
        data=application_data(require_application(db, row.id), merchant.name),
    )


@router.get("")
def list_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    application_status: str = Query("", alias="status"),
    merchant_id: int | None = None,
    keyword: str = "",
    data_scope: str = Query("real", pattern="^(real|demo|all)$"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    conditions = []
    if user.role != "operator":
        conditions.append(ServiceApplication.merchant_id == user.merchant_id)
    else:
        if data_scope == "real":
            conditions.append(ServiceApplication.is_demo.is_(False))
        elif data_scope == "demo":
            conditions.append(ServiceApplication.is_demo.is_(True))
        if merchant_id:
            conditions.append(ServiceApplication.merchant_id == merchant_id)
    if application_status:
        conditions.append(ServiceApplication.status == application_status)
    statement = (
        select(ServiceApplication, Merchant.name)
        .join(Merchant, Merchant.id == ServiceApplication.merchant_id)
        .options(selectinload(ServiceApplication.events))
    )
    count_statement = select(func.count()).select_from(ServiceApplication).join(
        Merchant, Merchant.id == ServiceApplication.merchant_id
    )
    if keyword:
        conditions.append(
            or_(
                Merchant.name.contains(keyword),
                ServiceApplication.contact_name.contains(keyword),
                ServiceApplication.contact_phone.contains(keyword),
            )
        )
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    total = db.scalar(count_statement) or 0
    rows = db.execute(
        statement.order_by(ServiceApplication.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Envelope(
        data={
            "items": [application_data(row, merchant_name) for row, merchant_name in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    )


@router.get("/summary")
def application_summary(
    data_scope: str = Query("real", pattern="^(real|demo|all)$"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    statement = select(ServiceApplication.status, func.count()).group_by(
        ServiceApplication.status
    )
    if user.role != "operator":
        statement = statement.where(ServiceApplication.merchant_id == user.merchant_id)
    elif data_scope == "real":
        statement = statement.where(ServiceApplication.is_demo.is_(False))
    elif data_scope == "demo":
        statement = statement.where(ServiceApplication.is_demo.is_(True))
    counts = {status_name: count for status_name, count in db.execute(statement).all()}
    return Envelope(
        data={
            "counts": counts,
            "pending_count": counts.get("pending", 0),
            "active_count": sum(counts.get(item, 0) for item in ACTIVE_STATUSES),
        }
    )


@router.get("/{application_id}")
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    row = require_application(db, application_id)
    assert_merchant_access(user, row.merchant_id)
    merchant_name = db.scalar(select(Merchant.name).where(Merchant.id == row.merchant_id))
    return Envelope(data=application_data(row, merchant_name))


@router.patch("/{application_id}/status")
def change_application_status(
    application_id: int,
    payload: ApplicationStatusIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    row = require_application(db, application_id)
    assert_merchant_access(user, row.merchant_id)
    if user.role != "operator":
        if row.status != "pending" or payload.status != "canceled":
            raise HTTPException(status_code=403, detail="商户只能取消待处理申请")
    elif payload.status not in TRANSITIONS[row.status]:
        raise HTTPException(status_code=422, detail="不允许执行该状态转换")
    before = model_snapshot(row)
    old_status = row.status
    row.status = payload.status
    if payload.status in {"completed", "canceled"}:
        row.active_key = None
        row.completed_at = utc_now()
    event = ApplicationEvent(
        application_id=row.id,
        actor_user_id=user.id,
        event_type="status_changed",
        from_status=old_status,
        to_status=payload.status,
        note=payload.note,
    )
    db.add(event)
    db.flush()
    add_audit(
        db,
        user,
        "application.status_changed",
        "service_application",
        row.id,
        before=before,
        after=model_snapshot(row),
        request=request,
    )
    status_label = {
        "pending": "待处理",
        "processing": "办理中",
        "completed": "已完成",
        "canceled": "已取消",
    }[payload.status]
    resource_name = str((row.resource_snapshot or {}).get("name") or "服务申请")
    notification_kwargs = {
        "notification_type": "service_application_status_changed",
        "category": "service",
        "title": "服务申请状态已更新",
        "message": f"{resource_name}当前状态：{status_label}",
        "action": "open_service_application",
        "target_type": "service_application",
        "target_id": row.id,
        "dedupe_key": f"application_event:{event.id}",
        "is_demo": row.is_demo,
    }
    if user.role == "operator":
        notify_merchant_account(db, row.merchant_id, **notification_kwargs)
    else:
        notify_active_operators(db, **notification_kwargs)
    db.commit()
    return Envelope(
        message="申请状态已更新",
        data=application_data(require_application(db, row.id)),
    )


@router.post("/{application_id}/notes")
def add_application_note(
    application_id: int,
    payload: ApplicationNoteIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    row = require_application(db, application_id)
    assert_merchant_access(user, row.merchant_id)
    if user.role != "operator" and row.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=422, detail="已结束的申请不能再补充留言")
    event_type = "note" if user.role == "operator" else "merchant_note"
    event = ApplicationEvent(
        application_id=row.id,
        actor_user_id=user.id,
        event_type=event_type,
        from_status=row.status,
        to_status=row.status,
        note=payload.note,
    )
    db.add(event)
    db.flush()
    add_audit(
        db,
        user,
        "application.note_added" if user.role == "operator" else "application.merchant_note_added",
        "service_application",
        row.id,
        after={"event_id": event.id, "note": payload.note},
        request=request,
    )
    resource_name = str((row.resource_snapshot or {}).get("name") or "服务申请")
    if user.role == "operator":
        notify_merchant_account(
            db,
            row.merchant_id,
            notification_type="service_operator_note_added",
            category="service",
            title="服务申请有新的运营备注",
            message=f"{resource_name}新增了运营跟进信息，请点击查看",
            action="open_service_application",
            target_type="service_application",
            target_id=row.id,
            dedupe_key=f"application_event:{event.id}",
            is_demo=row.is_demo,
        )
    else:
        merchant_name = db.scalar(
            select(Merchant.name).where(Merchant.id == row.merchant_id)
        ) or "商户"
        notify_active_operators(
            db,
            notification_type="service_merchant_note_added",
            category="service",
            title="商户补充了服务申请留言",
            message=f"{merchant_name}为{resource_name}补充了留言，请点击查看",
            action="open_service_application",
            target_type="service_application",
            target_id=row.id,
            dedupe_key=f"application_event:{event.id}",
            is_demo=row.is_demo,
        )
    db.commit()
    return Envelope(
        message="跟进备注已添加",
        data=application_data(require_application(db, row.id)),
    )
