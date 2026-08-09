from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal
from .models import Merchant, User
from .routers.media import store_product_image


def run() -> None:
    migrated = 0
    product_ids_added = 0
    old_files: list[Path] = []
    with SessionLocal() as db:
        fallback_user = db.scalar(select(User).order_by(User.id))
        if not fallback_user:
            raise RuntimeError("没有可用于媒体回填的账号")
        merchants = db.scalars(select(Merchant).order_by(Merchant.id)).all()
        for merchant in merchants:
            changed = False
            products = [dict(item) for item in (merchant.products or [])]
            for product in products:
                if not product.get("id"):
                    product["id"] = uuid4().hex
                    product_ids_added += 1
                    changed = True
                image_url = product.get("image_url") or ""
                if product.get("image_id") or not image_url.startswith(
                    "/api/v1/uploads/products/"
                ):
                    product.pop("image_url", None)
                    continue
                filename = Path(image_url).name
                old_path = Path(get_settings().upload_dir) / "products" / filename
                if not old_path.is_file():
                    product.pop("image_url", None)
                    changed = True
                    continue
                content = old_path.read_bytes()
                upload = UploadFile(file=BytesIO(content), filename=filename)
                asset = store_product_image(
                    db,
                    merchant.id,
                    fallback_user,
                    upload,
                    content,
                )
                product["image_id"] = asset.id
                product.pop("image_url", None)
                migrated += 1
                changed = True
                old_files.append(old_path)
            if changed:
                merchant.products = products
        db.commit()
    for path in old_files:
        path.unlink(missing_ok=True)
    print(
        f"media backfill complete: migrated={migrated}, "
        f"product_ids_added={product_ids_added}"
    )


if __name__ == "__main__":
    run()
