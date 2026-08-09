from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..audit import add_audit, model_snapshot
from ..database import get_db
from ..deps import assert_merchant_access, assert_merchant_write_access, current_user
from ..models import BusinessData, MediaAsset, Merchant, ServiceResource, User, utc_now
from ..rules import build_profile, recommend
from ..schemas import Envelope, MediaOut, MerchantOut, MerchantUpdate
from ..upload_security import read_upload_limited
from .media import MAX_PRODUCT_IMAGE_BYTES, media_path, store_product_image

router = APIRouter(prefix="/merchants", tags=["商户"])


def require_merchant(db: Session, merchant_id: int) -> Merchant:
    merchant = db.get(Merchant, merchant_id)
    if not merchant:
        raise HTTPException(status_code=404, detail="商户不存在")
    return merchant


@router.get("")
def list_merchants(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str = "",
    industry: str = "",
    merchant_status: str = Query("", alias="status"),
    data_scope: str = Query("all", pattern="^(all|real|demo)$"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    statement = select(Merchant)
    count_statement = select(func.count()).select_from(Merchant)
    conditions = []
    if user.role != "operator":
        conditions.append(Merchant.id == user.merchant_id)
    elif data_scope == "real":
        conditions.append(Merchant.is_demo.is_(False))
    elif data_scope == "demo":
        conditions.append(Merchant.is_demo.is_(True))
    if keyword:
        conditions.append(or_(Merchant.name.contains(keyword), Merchant.address.contains(keyword)))
    if industry:
        conditions.append(Merchant.industry == industry)
    if merchant_status:
        conditions.append(Merchant.status == merchant_status)
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    total = db.scalar(count_statement) or 0
    rows = db.scalars(
        statement.order_by(Merchant.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Envelope(
        data={
            "items": [MerchantOut.model_validate(row).model_dump() for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    )


@router.get("/{merchant_id}", response_model=Envelope[MerchantOut])
def get_merchant(
    merchant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_merchant_access(user, merchant_id)
    return Envelope(data=MerchantOut.model_validate(require_merchant(db, merchant_id)))


@router.put("/{merchant_id}", response_model=Envelope[MerchantOut])
def update_merchant(
    merchant_id: int,
    payload: MerchantUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_merchant_write_access(user, merchant_id)
    merchant = require_merchant(db, merchant_id)
    before = model_snapshot(merchant)
    data = payload.model_dump()
    if user.role != "operator":
        data["status"] = merchant.status
        data["is_demo"] = merchant.is_demo
    old_media_ids = {
        item.get("image_id") for item in merchant.products or [] if item.get("image_id")
    }
    new_media_ids = {
        item.get("image_id") for item in data.get("products", []) if item.get("image_id")
    }
    if new_media_ids:
        assets = db.scalars(select(MediaAsset).where(MediaAsset.id.in_(new_media_ids))).all()
        valid_ids = {
            asset.id
            for asset in assets
            if asset.merchant_id == merchant_id and asset.deleted_at is None
        }
        if valid_ids != new_media_ids:
            raise HTTPException(status_code=422, detail="商品图片不存在或不属于当前商户")
    removed_assets = []
    for media_id in old_media_ids - new_media_ids:
        asset = db.get(MediaAsset, media_id)
        if asset and not asset.deleted_at:
            asset.deleted_at = utc_now()
            removed_assets.append(asset)
    for key, value in data.items():
        setattr(merchant, key, value)
    add_audit(
        db,
        user,
        "merchant.updated",
        "merchant",
        merchant.id,
        before=before,
        after=model_snapshot(merchant),
        request=request,
    )
    db.commit()
    for asset in removed_assets:
        media_path(asset).unlink(missing_ok=True)
    db.refresh(merchant)
    return Envelope(message="商户资料已更新", data=MerchantOut.model_validate(merchant))


@router.post("/{merchant_id}/product-images", response_model=Envelope[MediaOut])
async def upload_product_image(
    merchant_id: int,
    request: Request,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_merchant_write_access(user, merchant_id)
    require_merchant(db, merchant_id)
    content = await read_upload_limited(
        image,
        MAX_PRODUCT_IMAGE_BYTES,
        label="商品图片",
    )
    asset = store_product_image(db, merchant_id, user, image, content)
    add_audit(
        db,
        user,
        "media.uploaded",
        "media_asset",
        asset.id,
        after=model_snapshot(asset),
        request=request,
    )
    try:
        db.commit()
    except Exception:
        media_path(asset).unlink(missing_ok=True)
        raise
    db.refresh(asset)
    return Envelope(message="图片上传成功", data=MediaOut.model_validate(asset))


def active_business_rows(db: Session, merchant_id: int, since: date | None = None):
    statement = select(BusinessData).where(
        BusinessData.merchant_id == merchant_id,
        BusinessData.is_deleted.is_(False),
    )
    if since:
        statement = statement.where(BusinessData.business_date >= since)
    return db.scalars(statement.order_by(BusinessData.business_date)).all()


@router.get("/{merchant_id}/business-summary")
def business_summary(
    merchant_id: int,
    days: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_merchant_access(user, merchant_id)
    require_merchant(db, merchant_id)
    rows = active_business_rows(db, merchant_id, date.today() - timedelta(days=days - 1))
    latest = rows[-1] if rows else None
    total_orders = sum(row.orders for row in rows)
    sources = {
        "到店消费": sum(row.dine_in_orders for row in rows),
        "外卖平台": sum(row.delivery_orders for row in rows),
        "短视频团购": sum(row.group_buy_orders for row in rows),
        "其他渠道": sum(row.other_orders for row in rows),
    }
    peaks: dict[int, int] = {}
    for row in rows:
        peaks[row.peak_hour] = peaks.get(row.peak_hour, 0) + row.orders
    revenue = round(sum(row.revenue for row in rows), 2)
    return Envelope(
        data={
            "days": days,
            "today": {
                "visitors": latest.visitors if latest else 0,
                "orders": latest.orders if latest else 0,
                "revenue": latest.revenue if latest else 0,
                "rating": latest.rating if latest else 0,
            },
            "totals": {
                "visitors": sum(row.visitors for row in rows),
                "orders": total_orders,
                "revenue": revenue,
                "average_order_value": round(revenue / total_orders, 2) if total_orders else 0,
            },
            "trend": [
                {
                    "date": row.business_date.isoformat(),
                    "revenue": row.revenue,
                    "visitors": row.visitors,
                    "orders": row.orders,
                }
                for row in rows
            ],
            "sources": [{"name": name, "value": value} for name, value in sources.items()],
            "peak_hours": [
                {"hour": f"{hour:02d}:00", "orders": orders}
                for hour, orders in sorted(peaks.items())
            ],
        }
    )


@router.get("/{merchant_id}/profile")
def merchant_profile(
    merchant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_merchant_access(user, merchant_id)
    merchant = require_merchant(db, merchant_id)
    return Envelope(data=build_profile(merchant, list(active_business_rows(db, merchant_id))))


@router.get("/{merchant_id}/recommendations")
def recommendations(
    merchant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_merchant_access(user, merchant_id)
    merchant = require_merchant(db, merchant_id)
    resources = db.scalars(
        select(ServiceResource).where(ServiceResource.status == "enabled")
    ).all()
    return Envelope(data=recommend(merchant, list(resources)))
