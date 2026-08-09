from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..audit import add_audit
from ..credential_storage import decrypt_file, delete_encrypted_file
from ..database import get_db
from ..deps import password_ready_user
from ..models import CredentialDocument, MerchantOnboardingApplication, User, utc_now
from ..schemas import Envelope

router = APIRouter(prefix="/credential-documents", tags=["入驻资质材料"])


def _document_and_application(
    db: Session, document_id: int
) -> tuple[CredentialDocument, MerchantOnboardingApplication]:
    document = db.get(CredentialDocument, document_id)
    if not document or document.deleted_at:
        raise HTTPException(status_code=404, detail="资质文件不存在")
    application = db.get(MerchantOnboardingApplication, document.application_id)
    if not application:
        raise HTTPException(status_code=404, detail="入驻申请不存在")
    return document, application


def _assert_view_access(user: User, application: MerchantOnboardingApplication) -> None:
    if user.role != "operator" and application.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权查看该资质文件")


@router.get("/{document_id}/content")
def document_content(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(password_ready_user),
):
    document, application = _document_and_application(db, document_id)
    _assert_view_access(user, application)
    content = decrypt_file(document.storage_key)
    add_audit(
        db,
        user,
        "credential_document.viewed",
        "credential_document",
        document.id,
        after={
            "application_id": application.id,
            "document_type": document.document_type,
        },
        request=request,
    )
    db.commit()
    return Response(
        content=content,
        media_type=document.mime_type,
        headers={
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
            "Content-Disposition": "inline",
        },
    )


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(password_ready_user),
):
    document, application = _document_and_application(db, document_id)
    if application.user_id != user.id:
        raise HTTPException(status_code=403, detail="仅申请人可以删除资质文件")
    if application.status not in {"draft", "needs_changes"}:
        raise HTTPException(status_code=409, detail="当前申请状态不允许删除材料")
    document.deleted_at = utc_now()
    add_audit(
        db,
        user,
        "credential_document.deleted",
        "credential_document",
        document.id,
        after={
            "application_id": application.id,
            "document_type": document.document_type,
        },
        request=request,
    )
    db.commit()
    delete_encrypted_file(document.storage_key)
    return Envelope(message="资质文件已删除", data={"id": document.id})
