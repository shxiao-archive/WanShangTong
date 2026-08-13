from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import BROWSER_SESSION_HEADER, SESSION_COOKIE_NAME, decode_access_token

bearer = HTTPBearer(auto_error=False)
PORTAL_HEADER = "x-wst2-portal"
PORTAL_ROLES = {"merchant", "operator"}


def requested_portal_role(request: Request) -> str | None:
    role = request.headers.get(PORTAL_HEADER, "").strip().lower()
    return role if role in PORTAL_ROLES else None


def enforce_portal_role(request: Request, user_role: str) -> None:
    portal_role = requested_portal_role(request)
    if portal_role and portal_role != user_role:
        target = "管理端" if user_role == "operator" else "商户端"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"该账号请前往{target}登录",
        )


def authenticated_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials else None
    if not token and request.headers.get(BROWSER_SESSION_HEADER) == "1":
        token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (InvalidTokenError, ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效") from None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    if int(payload.get("ver", 0)) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")
    enforce_portal_role(request, user.role)
    request.state.user_id = user.id
    return user


def password_ready_user(user: User = Depends(authenticated_user)) -> User:
    if user.must_change_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请先修改初始密码")
    return user


def current_user(user: User = Depends(password_ready_user)) -> User:
    if user.role == "merchant" and user.merchant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请先完成店铺入驻审核")
    return user


def onboarding_user(user: User = Depends(password_ready_user)) -> User:
    if user.role != "merchant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅商户账号可提交入驻申请")
    return user


def operator_only(user: User = Depends(current_user)) -> User:
    if user.role != "operator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅运营人员可执行此操作")
    return user


def assert_merchant_access(user: User, merchant_id: int) -> None:
    if user.role != "operator" and user.merchant_id != merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问其他商户数据")


def assert_merchant_write_access(user: User, merchant_id: int) -> None:
    if user.role != "merchant" or user.merchant_id != merchant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理人员仅可查看商户档案和经营数据",
        )
