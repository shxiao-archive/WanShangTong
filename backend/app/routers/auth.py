import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agreements import PRIVACY_VERSION, RULES_VERSION
from ..audit import add_audit, model_snapshot, request_client_ip
from ..config import get_settings
from ..database import get_db
from ..deps import authenticated_user, operator_only
from ..models import OperatorInvite, User, UserConsent, utc_now
from ..schemas import (
    ChangePasswordIn,
    Envelope,
    LoginIn,
    OperatorInviteOut,
    RegisterIn,
    UserOut,
    validate_password_strength,
)
from ..security import (
    BROWSER_SESSION_HEADER,
    SESSION_COOKIE_NAME,
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["认证"])
attempts: dict[str, deque] = defaultdict(deque)
registration_attempts: dict[str, deque] = defaultdict(deque)


def login_result(user: User, request: Request, response: Response) -> dict:
    token = create_access_token(user.id, user.role, user.token_version)
    settings = get_settings()
    browser_session = request.headers.get(BROWSER_SESSION_HEADER) == "1"
    if browser_session:
        response.set_cookie(
            SESSION_COOKIE_NAME,
            token,
            max_age=settings.jwt_expire_minutes * 60,
            httponly=True,
            secure=settings.environment == "production",
            samesite="strict",
            path="/api/v1",
        )
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    result = {
        "expires_in": settings.jwt_expire_minutes * 60,
        "user": UserOut.model_validate(user).model_dump(),
    }
    # Browser sessions receive the JWT only as an HttpOnly cookie. Bearer
    # clients retain the token response for API compatibility.
    if not browser_session:
        result.update({"access_token": token, "token_type": "bearer"})
    return result


def enforce_minute_limit(
    request: Request,
    buckets: dict[str, deque],
    maximum: int,
    message: str,
) -> deque:
    client = request_client_ip(request) or "unknown"
    monotonic_now = time.monotonic()
    window = buckets[client]
    while window and monotonic_now - window[0] > 60:
        window.popleft()
    if len(window) >= maximum:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)
    window.append(monotonic_now)
    return window


@router.post("/login")
def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    window = enforce_minute_limit(
        request,
        attempts,
        get_settings().login_attempts_per_minute,
        "登录尝试过于频繁，请稍后再试",
    )
    user = db.scalar(select(User).where(User.username == payload.username))
    now = utc_now()
    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=423, detail="账号已临时锁定，请 15 分钟后重试")
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        if user and user.is_active:
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                user.locked_until = now + timedelta(minutes=15)
                user.failed_login_count = 0
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    window.clear()
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()
    db.refresh(user)
    return Envelope(data=login_result(user, request, response))


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    enforce_minute_limit(
        request,
        registration_attempts,
        5,
        "注册尝试过于频繁，请稍后再试",
    )
    username = payload.username.strip()
    if not payload.accepted_rules or payload.rules_version != RULES_VERSION:
        raise HTTPException(status_code=422, detail="请阅读并同意当前版本的平台服务规则")
    if not payload.accepted_privacy or payload.privacy_version != PRIVACY_VERSION:
        raise HTTPException(status_code=422, detail="请阅读并同意当前版本的隐私政策")
    if db.scalar(select(User.id).where(User.username == username)):
        raise HTTPException(status_code=409, detail="登录账号已存在")

    invite: OperatorInvite | None = None
    if payload.account_type == "operator":
        code_hash = hashlib.sha256(payload.invitation_code.strip().encode()).hexdigest()
        invite = db.scalar(
            select(OperatorInvite)
            .where(
                OperatorInvite.code_hash == code_hash,
                OperatorInvite.used_at.is_(None),
                OperatorInvite.expires_at > utc_now(),
            )
            .with_for_update()
        )
        if not invite:
            raise HTTPException(status_code=422, detail="邀请码无效、已使用或已过期")
    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(),
        role=payload.account_type,
        merchant_id=None,
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    ip_value = request_client_ip(request)
    ip_hash = hashlib.sha256(ip_value.encode()).hexdigest() if ip_value else ""
    user_agent = request.headers.get("user-agent", "")
    user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest() if user_agent else ""
    db.add_all(
        [
            UserConsent(
                user_id=user.id,
                agreement_type="platform_rules",
                version=RULES_VERSION,
                ip_hash=ip_hash,
                user_agent_hash=user_agent_hash,
            ),
            UserConsent(
                user_id=user.id,
                agreement_type="privacy_policy",
                version=PRIVACY_VERSION,
                ip_hash=ip_hash,
                user_agent_hash=user_agent_hash,
            ),
        ]
    )
    if invite:
        invite.used_by = user.id
        invite.used_at = utc_now()
    add_audit(
        db,
        user,
        "user.self_registered",
        "user",
        user.id,
        after={
            **model_snapshot(user),
            "registration_type": payload.account_type,
            "invitation_id": invite.id if invite else None,
        },
        request=request,
    )
    db.commit()
    db.refresh(user)
    return Envelope(
        message="账号注册成功",
        data=login_result(user, request, response),
    )


@router.post(
    "/operator-invites",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[OperatorInviteOut],
)
def create_operator_invite(
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(operator_only),
):
    invitation_code = f"WST-{secrets.token_urlsafe(24)}"
    invite = OperatorInvite(
        code_hash=hashlib.sha256(invitation_code.encode()).hexdigest(),
        created_by=operator.id,
        expires_at=utc_now() + timedelta(hours=24),
    )
    db.add(invite)
    db.flush()
    add_audit(
        db,
        operator,
        "operator_invite.created",
        "operator_invite",
        invite.id,
        after=model_snapshot(invite),
        request=request,
    )
    db.commit()
    return Envelope(
        message="管理人员邀请码已生成",
        data=OperatorInviteOut(
            invitation_code=invitation_code,
            expires_at=invite.expires_at,
        ),
    )


@router.get("/me", response_model=Envelope[UserOut])
def me(response: Response, user: User = Depends(authenticated_user)):
    response.headers["Cache-Control"] = "no-store, private"
    return Envelope(data=UserOut.model_validate(user))


@router.post("/logout")
def logout(response: Response):
    settings = get_settings()
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/api/v1",
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store, private"
    return Envelope(message="已退出登录", data={"logged_out": True})


@router.post("/change-password")
def change_password(
    payload: ChangePasswordIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=422, detail="当前密码不正确")
    try:
        validate_password_strength(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.token_version += 1
    add_audit(
        db,
        user,
        "auth.password_changed",
        "user",
        user.id,
        after={"must_change_password": False, "token_version": user.token_version},
        request=request,
    )
    db.commit()
    db.refresh(user)
    return Envelope(
        message="密码已修改",
        data=login_result(user, request, response),
    )
