import json
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import operator_only
from ..models import User
from ..schemas import Envelope

router = APIRouter(prefix="/system", tags=["系统"])


@router.get("/status")
def system_status(
    db: Session = Depends(get_db),
    _: User = Depends(operator_only),
):
    db.execute(text("SELECT 1"))
    upload_dir = Path(get_settings().upload_dir)
    disk = shutil.disk_usage(upload_dir)
    manifest_path = Path(get_settings().backup_status_file)
    latest_backup = None
    if manifest_path.is_file():
        try:
            latest_backup = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            latest_backup = {"status": "invalid_manifest"}
    return Envelope(
        data={
            "database": "healthy",
            "uploads_writable": upload_dir.is_dir() and os_access_writable(upload_dir),
            "disk": {
                "total_bytes": disk.total,
                "free_bytes": disk.free,
                "used_percent": round((disk.used / disk.total) * 100, 1),
            },
            "latest_backup": latest_backup,
        }
    )


def os_access_writable(path: Path) -> bool:
    import os

    return os.access(path, os.W_OK)
