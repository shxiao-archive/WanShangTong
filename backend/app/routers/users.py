from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import add_audit, model_snapshot
from ..database import get_db
from ..deps import operator_only
from ..models import Merchant, User
from ..schemas import (
    Envelope,
    TemporaryPasswordOut,
    UserOut,
    UserStatusIn,
)
from ..security import generate_temporary_password, hash_password

router = APIRouter(prefix="/users", tags=["账号"])


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(operator_only),
):
    rows = db.execute(
        select(User, Merchant.name)
        .outerjoin(Merchant, Merchant.id == User.merchant_id)
        .order_by(User.id)
    ).all()
    return Envelope(
        data=[
            {
                **UserOut.model_validate(user).model_dump(),
                "merchant_name": merchant_name,
            }
            for user, merchant_name in rows
        ]
    )


@router.post("/{user_id}/reset-password", response_model=Envelope[TemporaryPasswordOut])
def reset_password(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(operator_only),
):
    user = db.get(User, user_id)
    if not user or user.role != "merchant":
        raise HTTPException(status_code=404, detail="商户账号不存在")
    temporary_password = generate_temporary_password()
    before = model_snapshot(user)
    user.password_hash = hash_password(temporary_password)
    user.must_change_password = True
    user.token_version += 1
    user.failed_login_count = 0
    user.locked_until = None
    add_audit(
        db,
        operator,
        "user.password_reset",
        "user",
        user.id,
        before=before,
        after=model_snapshot(user),
        request=request,
    )
    db.commit()
    db.refresh(user)
    return Envelope(
        message="临时密码已重置",
        data=TemporaryPasswordOut(
            user=UserOut.model_validate(user),
            temporary_password=temporary_password,
        ),
    )


@router.patch("/{user_id}/status", response_model=Envelope[UserOut])
def change_user_status(
    user_id: int,
    payload: UserStatusIn,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(operator_only),
):
    user = db.get(User, user_id)
    if not user or user.role != "merchant":
        raise HTTPException(status_code=404, detail="商户账号不存在")
    before = model_snapshot(user)
    user.is_active = payload.is_active
    if not payload.is_active:
        user.token_version += 1
    add_audit(
        db,
        operator,
        "user.status_changed",
        "user",
        user.id,
        before=before,
        after=model_snapshot(user),
        request=request,
    )
    db.commit()
    db.refresh(user)
    return Envelope(message="账号状态已更新", data=UserOut.model_validate(user))
