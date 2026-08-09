from fastapi import APIRouter

from ..agreements import AGREEMENTS
from ..schemas import Envelope

router = APIRouter(prefix="/legal", tags=["平台协议"])


@router.get("/agreements/current")
def current_agreements():
    return Envelope(data=AGREEMENTS)
