import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..audit import add_audit, model_snapshot
from ..config import get_settings
from ..database import get_db
from ..deps import assert_merchant_access, assert_merchant_write_access, current_user
from ..models import MediaAsset, Merchant, User, utc_now
from ..schemas import Envelope, MediaOut
from ..upload_security import PRODUCT_IMAGE_FORMATS, normalize_image, safe_upload_path

router = APIRouter(prefix="/media", tags=["媒体"])
MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024


def media_path(asset: MediaAsset) -> Path:
    return safe_upload_path(
        get_settings().upload_dir,
        asset.storage_key,
        required_prefix="products",
    )


def store_product_image(
    db: Session,
    merchant_id: int,
    user: User,
    upload: UploadFile,
    content: bytes,
) -> MediaAsset:
    if not content:
        raise HTTPException(status_code=422, detail="商品图片不能为空")
    if len(content) > MAX_PRODUCT_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="商品图片不能超过 10MB")
    normalized, _ = normalize_image(
        upload,
        content,
        maximum_edge=2000,
        output_format="WEBP",
        allowed_formats=PRODUCT_IMAGE_FORMATS,
    )
    storage_key = f"products/{uuid4().hex}.webp"
    target = safe_upload_path(
        get_settings().upload_dir,
        storage_key,
        required_prefix="products",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(normalized)
    target.chmod(0o600)
    asset = MediaAsset(
        merchant_id=merchant_id,
        storage_key=storage_key,
        original_name=Path(upload.filename or "product-image").name[:255],
        mime_type="image/webp",
        file_size=len(normalized),
        sha256=hashlib.sha256(normalized).hexdigest(),
        uploaded_by=user.id,
    )
    db.add(asset)
    db.flush()
    return asset


@router.get("/{media_id}/content")
def media_content(
    media_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    asset = db.get(MediaAsset, media_id)
    if not asset or asset.deleted_at:
        raise HTTPException(status_code=404, detail="图片不存在")
    assert_merchant_access(user, asset.merchant_id)
    path = media_path(asset)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在")
    return FileResponse(
        path,
        media_type=asset.mime_type,
        headers={
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{media_id}")
def delete_media(
    media_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    asset = db.get(MediaAsset, media_id)
    if not asset or asset.deleted_at:
        raise HTTPException(status_code=404, detail="图片不存在")
    assert_merchant_write_access(user, asset.merchant_id)
    merchant = db.get(Merchant, asset.merchant_id)
    if merchant and any(item.get("image_id") == asset.id for item in merchant.products or []):
        raise HTTPException(status_code=409, detail="图片仍被商品使用，请先移除商品图片")
    before = model_snapshot(asset)
    asset.deleted_at = utc_now()
    add_audit(
        db,
        user,
        "media.deleted",
        "media_asset",
        asset.id,
        before=before,
        after=model_snapshot(asset),
        request=request,
    )
    db.commit()
    media_path(asset).unlink(missing_ok=True)
    return Envelope(message="图片已彻底删除", data={"id": asset.id})
