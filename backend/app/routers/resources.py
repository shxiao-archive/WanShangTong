from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..audit import add_audit, model_snapshot
from ..deps import current_user, operator_only
from ..models import ServiceApplication, ServiceResource, User
from ..schemas import Envelope, ResourceCreate, ResourceOut, ResourceUpdate, StatusIn

router = APIRouter(prefix="/resources", tags=["资源"])


@router.get("")
def list_resources(
    resource_status: str = Query("", alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    statement = select(ServiceResource)
    if user.role != "operator":
        statement = statement.where(ServiceResource.status == "enabled")
    elif resource_status:
        statement = statement.where(ServiceResource.status == resource_status)
    rows = db.scalars(statement.order_by(ServiceResource.id)).all()
    subscription_counts: dict[int, int] = {}
    if user.role == "operator":
        subscription_counts = {
            resource_id: amount
            for resource_id, amount in db.execute(
                select(
                    ServiceApplication.resource_id,
                    func.count(func.distinct(ServiceApplication.merchant_id)),
                )
                .where(
                    ServiceApplication.status == "completed",
                    ServiceApplication.is_demo.is_(False),
                )
                .group_by(ServiceApplication.resource_id)
            ).all()
        }
    return Envelope(
        data=[
            {
                **ResourceOut.model_validate(row).model_dump(),
                "subscription_count": subscription_counts.get(row.id, 0),
            }
            for row in rows
        ]
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_resource(
    payload: ResourceCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(operator_only),
):
    row = ServiceResource(**payload.model_dump())
    db.add(row)
    db.flush()
    add_audit(db, user, "resource.created", "service_resource", row.id, after=model_snapshot(row), request=request)
    db.commit()
    db.refresh(row)
    return Envelope(message="资源创建成功", data=ResourceOut.model_validate(row))


@router.put("/{resource_id}")
def update_resource(
    resource_id: int,
    payload: ResourceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(operator_only),
):
    row = db.get(ServiceResource, resource_id)
    if not row:
        raise HTTPException(status_code=404, detail="资源不存在")
    before = model_snapshot(row)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    add_audit(db, user, "resource.updated", "service_resource", row.id, before=before, after=model_snapshot(row), request=request)
    db.commit()
    db.refresh(row)
    return Envelope(message="资源已更新", data=ResourceOut.model_validate(row))


@router.patch("/{resource_id}/status")
def change_status(
    resource_id: int,
    payload: StatusIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(operator_only),
):
    if payload.status not in {"enabled", "disabled"}:
        raise HTTPException(status_code=422, detail="状态只能是 enabled 或 disabled")
    row = db.get(ServiceResource, resource_id)
    if not row:
        raise HTTPException(status_code=404, detail="资源不存在")
    before = model_snapshot(row)
    row.status = payload.status
    add_audit(db, user, "resource.status_changed", "service_resource", row.id, before=before, after=model_snapshot(row), request=request)
    db.commit()
    return Envelope(message="资源状态已更新", data={"id": resource_id, "status": row.status})
