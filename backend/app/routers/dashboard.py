from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import operator_only
from ..models import Merchant, ServiceApplication, User
from ..rules import overview
from ..schemas import Envelope

router = APIRouter(prefix="/dashboard", tags=["运营看板"])


@router.get("/overview")
def dashboard_overview(
    data_scope: str = "real",
    db: Session = Depends(get_db),
    _: User = Depends(operator_only),
):
    statement = select(Merchant)
    if data_scope == "real":
        statement = statement.where(Merchant.is_demo.is_(False))
    elif data_scope == "demo":
        statement = statement.where(Merchant.is_demo.is_(True))
    elif data_scope != "all":
        data_scope = "real"
        statement = statement.where(Merchant.is_demo.is_(False))
    merchants = db.scalars(statement).all()
    result = overview(list(merchants))
    application_statement = select(func.count()).select_from(ServiceApplication).where(
        ServiceApplication.status == "pending"
    )
    if data_scope == "real":
        application_statement = application_statement.where(
            ServiceApplication.is_demo.is_(False)
        )
    elif data_scope == "demo":
        application_statement = application_statement.where(
            ServiceApplication.is_demo.is_(True)
        )
    result["pending_application_count"] = db.scalar(application_statement) or 0
    result["demo_merchant_count"] = (
        db.scalar(
            select(func.count()).select_from(Merchant).where(Merchant.is_demo.is_(True))
        )
        or 0
    )
    result["data_scope"] = data_scope
    return Envelope(data=result)
