import hashlib
import re
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..agreements import PRIVACY_VERSION, RULES_VERSION
from ..audit import add_audit, model_snapshot, request_client_ip
from ..credential_storage import (
    MAX_CREDENTIAL_BYTES,
    delete_encrypted_file,
    encrypt_upload,
)
from ..database import get_db
from ..deps import onboarding_user, operator_only
from ..models import (
    CredentialDocument,
    LegalEntity,
    Merchant,
    MerchantOnboardingApplication,
    User,
    UserConsent,
    utc_now,
)
from ..notifications import (
    add_notification,
    mark_related_notifications_read,
    notify_active_operators,
)
from ..schemas import (
    CredentialDocumentOut,
    Envelope,
    MerchantOnboardingDraftIn,
    MerchantOnboardingIn,
    MerchantOnboardingOut,
    MerchantOnboardingReviewIn,
    MerchantOnboardingSubmitIn,
    normalize_and_validate_uscc,
    validate_uscc_subject_type,
)
from ..upload_security import read_upload_limited

router = APIRouter(prefix="/merchant-onboarding", tags=["商户入驻"])

DOCUMENT_TYPES = {
    "business_license",
    "authorization_letter",
    "food_business_license",
    "prepackaged_food_filing",
    "accommodation_permit",
    "other_permit",
}
SINGLE_DOCUMENT_TYPES = DOCUMENT_TYPES - {"other_permit"}
DRAFT_FIELDS = tuple(MerchantOnboardingDraftIn.model_fields)


def _blank_application(user: User) -> MerchantOnboardingApplication:
    return MerchantOnboardingApplication(
        user_id=user.id,
        merchant_name="",
        industry="",
        phone="",
        address="",
        business_hours="09:00-21:00",
        contact_name=user.display_name,
        scale="小微",
        employee_count=3,
        store_area=60,
        network_environment="普通宽带",
        bandwidth_mbps=100,
        needs=[],
        additional_permits=[],
        status="draft",
    )


def _get_or_create_draft(
    db: Session, user: User, *, lock: bool = False
) -> MerchantOnboardingApplication:
    statement = select(MerchantOnboardingApplication).where(
        MerchantOnboardingApplication.user_id == user.id
    )
    if lock:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if not row:
        row = _blank_application(user)
        db.add(row)
        db.flush()
    return row


def _active_documents(
    db: Session, application_id: int
) -> list[CredentialDocument]:
    return list(
        db.scalars(
            select(CredentialDocument)
            .where(
                CredentialDocument.application_id == application_id,
                CredentialDocument.deleted_at.is_(None),
            )
            .order_by(CredentialDocument.id)
        )
    )


def application_data(
    db: Session,
    row: MerchantOnboardingApplication,
    user: User | None = None,
) -> dict:
    data = {field: getattr(row, field) for field in DRAFT_FIELDS}
    # Applications created before the five-step onboarding flow legitimately
    # have NULL in newly added draft columns. Keep those rows readable so an
    # operator can request the missing material instead of failing the list.
    for field_name, model_field in MerchantOnboardingDraftIn.model_fields.items():
        if data[field_name] is None:
            data[field_name] = model_field.get_default(call_default_factory=True)
    for optional_enum in (
        "subject_type",
        "industry",
        "contact_relationship",
        "retail_food_credential_type",
    ):
        if not data.get(optional_enum):
            data[optional_enum] = None
    data["additional_permits"] = data.get("additional_permits") or []
    data.update(
        {
            "id": row.id,
            "user_id": row.user_id,
            "username": user.username if user else "",
            "display_name": user.display_name if user else "",
            "status": row.status,
            "review_note": row.review_note,
            "reviewed_by": row.reviewed_by,
            "reviewed_at": row.reviewed_at,
            "submitted_at": row.submitted_at,
            "truthfulness_confirmed": row.truthfulness_confirmed,
            "rules_version": row.rules_version,
            "privacy_version": row.privacy_version,
            "documents": [
                CredentialDocumentOut.model_validate(item).model_dump()
                for item in _active_documents(db, row.id)
            ],
            "existing_entity": None,
            "duplicate_store": False,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )
    if row.unified_social_credit_code:
        entity = db.scalar(
            select(LegalEntity).where(
                LegalEntity.unified_social_credit_code
                == row.unified_social_credit_code
            )
        )
        if entity:
            merchant_count = db.scalar(
                select(func.count())
                .select_from(Merchant)
                .where(Merchant.legal_entity_id == entity.id)
            ) or 0
            data["existing_entity"] = {
                "id": entity.id,
                "legal_name": entity.legal_name,
                "merchant_count": merchant_count,
            }
            normalized_name = row.merchant_name.strip()
            normalized_address = row.address.strip()
            data["duplicate_store"] = bool(
                db.scalar(
                    select(Merchant.id).where(
                        Merchant.legal_entity_id == entity.id,
                        Merchant.name == normalized_name,
                        Merchant.address == normalized_address,
                    )
                )
            )
    return MerchantOnboardingOut.model_validate(data).model_dump()


def _document_map(documents: list[CredentialDocument]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for document in documents:
        result.setdefault(document.document_type, []).append(document.id)
    return result


def _submission_errors(
    row: MerchantOnboardingApplication,
    documents: list[CredentialDocument],
    payload: MerchantOnboardingSubmitIn,
) -> list[dict]:
    errors: list[dict] = []

    def require(step: int, field: str, value, message: str) -> None:
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append({"step": step, "field": field, "message": message})

    require(0, "subject_type", row.subject_type, "请选择主体类型")
    require(0, "legal_name", row.legal_name, "请填写营业执照名称")
    require(
        0,
        "unified_social_credit_code",
        row.unified_social_credit_code,
        "请填写统一社会信用代码",
    )
    require(
        0,
        "legal_representative",
        row.legal_representative,
        "请填写法定代表人或经营者姓名",
    )
    require(0, "registered_address", row.registered_address, "请填写注册地址")
    require(0, "business_scope", row.business_scope, "请填写营业执照经营范围")
    if row.unified_social_credit_code:
        try:
            validate_uscc_subject_type(
                row.unified_social_credit_code,
                row.subject_type,
            )
        except ValueError as exc:
            errors.append(
                {
                    "step": 0,
                    "field": "unified_social_credit_code",
                    "message": str(exc),
                }
            )

    require(1, "merchant_name", row.merchant_name, "请填写店铺展示名称")
    require(1, "industry", row.industry, "请选择所属行业")
    require(1, "address", row.address, "请填写实际经营地址")
    require(2, "contact_name", row.contact_name, "请填写联系人姓名")
    require(2, "phone", row.phone, "请填写联系电话")
    require(2, "contact_relationship", row.contact_relationship, "请选择联系人关系")
    if row.phone and not re.fullmatch(r"[0-9+() -]{7,30}", row.phone):
        errors.append(
            {"step": 2, "field": "phone", "message": "联系电话格式不正确"}
        )
    if row.contact_relationship in {"store_manager", "authorized_agent"}:
        if not row.authorization_confirmed:
            errors.append(
                {
                    "step": 2,
                    "field": "authorization_confirmed",
                    "message": "非主体本人提交时必须确认已获得授权",
                }
            )

    by_type = _document_map(documents)
    if "business_license" not in by_type:
        errors.append(
            {"step": 0, "field": "business_license", "message": "请上传营业执照"}
        )
    if row.industry == "餐饮" and "food_business_license" not in by_type:
        errors.append(
            {
                "step": 3,
                "field": "food_business_license",
                "message": "餐饮商户必须上传食品经营许可证",
            }
        )
    if row.industry == "住宿" and "accommodation_permit" not in by_type:
        errors.append(
            {
                "step": 3,
                "field": "accommodation_permit",
                "message": "住宿商户必须上传行业许可或备案材料",
            }
        )
    if row.industry == "零售" and row.retail_food_related:
        require(
            3,
            "retail_food_credential_type",
            row.retail_food_credential_type,
            "请选择食品经营许可类型",
        )
        if (
            row.retail_food_credential_type
            and row.retail_food_credential_type not in by_type
        ):
            errors.append(
                {
                    "step": 3,
                    "field": row.retail_food_credential_type,
                    "message": "请上传对应的食品经营许可或备案材料",
                }
            )
    if row.other_permit_required:
        require(3, "other_permit_name", row.other_permit_name, "请填写其他许可证名称")
        if "other_permit" not in by_type:
            errors.append(
                {
                    "step": 3,
                    "field": "other_permit",
                    "message": "请上传其他行政许可材料",
                }
            )
    active_ids = {document.id for document in documents}
    for index, permit in enumerate(row.additional_permits or []):
        if permit.get("document_id") not in active_ids:
            errors.append(
                {
                    "step": 3,
                    "field": f"additional_permits.{index}",
                    "message": "追加许可证缺少有效附件",
                }
            )

    if not payload.truthfulness_confirmed:
        errors.append(
            {
                "step": 4,
                "field": "truthfulness_confirmed",
                "message": "请确认所提交资料真实有效",
            }
        )
    if not payload.accepted_rules or payload.rules_version != RULES_VERSION:
        errors.append(
            {"step": 4, "field": "rules_version", "message": "请同意当前平台服务规则"}
        )
    if not payload.accepted_privacy or payload.privacy_version != PRIVACY_VERSION:
        errors.append(
            {"step": 4, "field": "privacy_version", "message": "请同意当前隐私政策"}
        )
    return errors


def _record_consents(
    db: Session,
    row: MerchantOnboardingApplication,
    user: User,
    request: Request,
) -> None:
    client_ip = request_client_ip(request)
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest() if client_ip else ""
    user_agent = request.headers.get("user-agent", "")
    user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest() if user_agent else ""
    for agreement_type, version in (
        ("application_truthfulness", "2026-07-29-v1"),
        ("platform_rules", RULES_VERSION),
        ("privacy_policy", PRIVACY_VERSION),
    ):
        db.add(
            UserConsent(
                user_id=user.id,
                application_id=row.id,
                agreement_type=agreement_type,
                version=version,
                ip_hash=ip_hash,
                user_agent_hash=user_agent_hash,
            )
        )


@router.get("/me")
def my_application(
    db: Session = Depends(get_db),
    user: User = Depends(onboarding_user),
):
    row = db.scalar(
        select(MerchantOnboardingApplication).where(
            MerchantOnboardingApplication.user_id == user.id
        )
    )
    return Envelope(data=application_data(db, row, user) if row else None)


@router.put("/me/draft")
def save_draft(
    payload: MerchantOnboardingDraftIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(onboarding_user),
):
    if user.merchant_id is not None:
        raise HTTPException(status_code=409, detail="账号已绑定商户，无需重复申请")
    row = _get_or_create_draft(db, user, lock=True)
    if row.status in {"pending", "approved"}:
        raise HTTPException(status_code=409, detail="当前申请状态不允许修改")
    before = model_snapshot(row)
    values = payload.model_dump()
    # The five-step wizard saves step 1 before the applicant has selected an
    # industry on step 2. The legacy column is still NOT NULL, so persist an
    # empty draft value and expose it back to the client as null.
    values["industry"] = payload.industry or ""
    values["additional_permits"] = [
        item.model_dump() for item in payload.additional_permits
    ]
    for key, value in values.items():
        setattr(row, key, value)
    row.truthfulness_confirmed = False
    add_audit(
        db,
        user,
        "merchant_onboarding.draft_saved",
        "merchant_onboarding_application",
        row.id,
        before=before,
        after=model_snapshot(row),
        request=request,
    )
    db.commit()
    db.refresh(row)
    return Envelope(message="草稿已保存", data=application_data(db, row, user))


@router.post("/me/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    document_type: str = Form(...),
    document_number: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(onboarding_user),
):
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail="不支持的资质文件类型")
    row = _get_or_create_draft(db, user, lock=True)
    if row.status not in {"draft", "needs_changes"}:
        raise HTTPException(status_code=409, detail="当前申请状态不允许上传材料")
    current = _active_documents(db, row.id)
    if len(current) >= 20:
        raise HTTPException(status_code=422, detail="每份入驻申请最多上传20个材料")

    content = await read_upload_limited(
        file,
        MAX_CREDENTIAL_BYTES,
        label="资质文件",
    )
    storage_key = ""
    replaced: list[CredentialDocument] = []
    try:
        storage_key, mime_type, file_size, sha256 = encrypt_upload(
            file, content
        )
        document = CredentialDocument(
            application_id=row.id,
            uploaded_by=user.id,
            document_type=document_type,
            document_number=document_number.strip()[:120],
            storage_key=storage_key,
            original_name=Path(file.filename or "credential").name[:255],
            mime_type=mime_type,
            file_size=file_size,
            sha256=sha256,
        )
        db.add(document)
        db.flush()
        if document_type in SINGLE_DOCUMENT_TYPES:
            replaced = [
                item for item in current if item.document_type == document_type
            ]
            for old in replaced:
                old.deleted_at = utc_now()
        add_audit(
            db,
            user,
            "credential_document.uploaded",
            "credential_document",
            document.id,
            after={
                "application_id": row.id,
                "document_type": document_type,
                "mime_type": mime_type,
                "file_size": file_size,
                "sha256": sha256,
            },
            request=request,
        )
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        if storage_key:
            delete_encrypted_file(storage_key)
        raise
    for old in replaced:
        delete_encrypted_file(old.storage_key)
    return Envelope(
        message="资质文件已安全上传",
        data=CredentialDocumentOut.model_validate(document),
    )


@router.post("/me/submit")
def submit_application(
    payload: MerchantOnboardingSubmitIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(onboarding_user),
):
    if user.merchant_id is not None:
        raise HTTPException(status_code=409, detail="账号已绑定商户，无需重复申请")
    row = _get_or_create_draft(db, user, lock=True)
    if row.status in {"pending", "approved"}:
        raise HTTPException(status_code=409, detail="当前申请已经提交")
    documents = _active_documents(db, row.id)
    errors = _submission_errors(row, documents, payload)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": errors[0]["message"], "data": {"errors": errors}},
        )
    was_resubmission = row.status == "needs_changes"
    before = model_snapshot(row)
    row.unified_social_credit_code = normalize_and_validate_uscc(
        row.unified_social_credit_code or ""
    )
    row.truthfulness_confirmed = True
    row.rules_version = RULES_VERSION
    row.privacy_version = PRIVACY_VERSION
    row.status = "pending"
    row.review_note = ""
    row.reviewed_by = None
    row.reviewed_at = None
    row.submitted_at = utc_now()
    _record_consents(db, row, user, request)
    add_audit(
        db,
        user,
        "merchant_onboarding.submitted",
        "merchant_onboarding_application",
        row.id,
        before=before,
        after=model_snapshot(row),
        request=request,
    )
    if was_resubmission:
        mark_related_notifications_read(
            db,
            recipient_user_id=user.id,
            notification_type="onboarding_needs_changes",
            target_type="merchant_onboarding_application",
            target_id=row.id,
        )
    notify_active_operators(
        db,
        notification_type=(
            "onboarding_resubmitted" if was_resubmission else "onboarding_submitted"
        ),
        category="onboarding",
        title="入驻资料已重新提交" if was_resubmission else "新的商户入驻申请",
        message=f"{row.merchant_name}已提交入驻资料，请及时审核",
        action="open_onboarding_review",
        target_type="merchant_onboarding_application",
        target_id=row.id,
        dedupe_key=f"onboarding:{row.id}:submitted:{row.submitted_at.isoformat()}",
        is_demo=False,
    )
    db.commit()
    db.refresh(row)
    return Envelope(message="店铺入驻申请已提交", data=application_data(db, row, user))


@router.post("/me", deprecated=True, status_code=status.HTTP_201_CREATED)
def legacy_submit_application(
    _: MerchantOnboardingIn,
    user: User = Depends(onboarding_user),
):
    raise HTTPException(
        status_code=422,
        detail="入驻申请已升级，请刷新页面后补充主体资质并重新提交",
    )


@router.get("")
def list_applications(
    application_status: str = Query(
        "pending", alias="status", pattern="^(draft|pending|approved|needs_changes|all)$"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(operator_only),
):
    statement = (
        select(MerchantOnboardingApplication, User)
        .join(User, User.id == MerchantOnboardingApplication.user_id)
    )
    count_statement = select(func.count()).select_from(MerchantOnboardingApplication)
    if application_status != "all":
        statement = statement.where(
            MerchantOnboardingApplication.status == application_status
        )
        count_statement = count_statement.where(
            MerchantOnboardingApplication.status == application_status
        )
    total = db.scalar(count_statement) or 0
    rows = db.execute(
        statement.order_by(MerchantOnboardingApplication.created_at)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Envelope(
        data={
            "items": [application_data(db, row, user) for row, user in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/summary")
def onboarding_summary(
    db: Session = Depends(get_db),
    _: User = Depends(operator_only),
):
    pending_filter = MerchantOnboardingApplication.status == "pending"
    pending_count = db.scalar(
        select(func.count())
        .select_from(MerchantOnboardingApplication)
        .where(pending_filter)
    ) or 0
    rows = db.execute(
        select(MerchantOnboardingApplication, User)
        .join(User, User.id == MerchantOnboardingApplication.user_id)
        .where(pending_filter)
        .order_by(
            MerchantOnboardingApplication.submitted_at.desc(),
            MerchantOnboardingApplication.id.desc(),
        )
        .limit(20)
    ).all()
    return Envelope(
        data={
            "pending_count": pending_count,
            "latest": [
                {
                    "id": row.id,
                    "merchant_name": row.merchant_name,
                    "username": user.username,
                    "submitted_at": row.submitted_at,
                }
                for row, user in rows
            ],
        }
    )


@router.get("/{application_id}")
def application_detail(
    application_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(operator_only),
):
    result = db.execute(
        select(MerchantOnboardingApplication, User)
        .join(User, User.id == MerchantOnboardingApplication.user_id)
        .where(MerchantOnboardingApplication.id == application_id)
    ).first()
    if not result:
        raise HTTPException(status_code=404, detail="入驻申请不存在")
    return Envelope(data=application_data(db, result[0], result[1]))


@router.patch("/{application_id}/review")
def review_application(
    application_id: int,
    payload: MerchantOnboardingReviewIn,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(operator_only),
):
    row = db.scalar(
        select(MerchantOnboardingApplication)
        .where(MerchantOnboardingApplication.id == application_id)
        .with_for_update()
    )
    if not row:
        raise HTTPException(status_code=404, detail="入驻申请不存在")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="该申请当前不在待审核状态")
    applicant = db.get(User, row.user_id)
    if not applicant or not applicant.is_active or applicant.role != "merchant":
        raise HTTPException(status_code=409, detail="申请账号不可用")
    if applicant.merchant_id is not None:
        raise HTTPException(status_code=409, detail="申请账号已经绑定商户")

    before = model_snapshot(row)
    if payload.action == "approve":
        documents = _active_documents(db, row.id)
        validation_payload = MerchantOnboardingSubmitIn(
            truthfulness_confirmed=row.truthfulness_confirmed,
            accepted_rules=True,
            rules_version=row.rules_version or "",
            accepted_privacy=True,
            privacy_version=row.privacy_version or "",
        )
        errors = _submission_errors(row, documents, validation_payload)
        if errors:
            raise HTTPException(status_code=409, detail=errors[0]["message"])

        entity = db.scalar(
            select(LegalEntity)
            .where(
                LegalEntity.unified_social_credit_code
                == row.unified_social_credit_code
            )
            .with_for_update()
        )
        if entity and entity.legal_name != row.legal_name.strip():
            raise HTTPException(
                status_code=409,
                detail="统一社会信用代码已存在，但主体名称不一致，请先要求申请人核对",
            )
        if entity and (
            entity.subject_type != row.subject_type
            or entity.legal_representative != row.legal_representative.strip()
            or entity.registered_address != row.registered_address.strip()
        ):
            raise HTTPException(
                status_code=409,
                detail="该主体已存在，但主体类型、代表人或注册地址不一致，请先核对",
            )
        if not entity:
            entity = LegalEntity(
                subject_type=row.subject_type or "",
                legal_name=row.legal_name.strip(),
                unified_social_credit_code=row.unified_social_credit_code or "",
                legal_representative=row.legal_representative.strip(),
                registered_address=row.registered_address.strip(),
                business_scope=row.business_scope.strip(),
                status="verified",
            )
            db.add(entity)
            db.flush()
            add_audit(
                db,
                operator,
                "legal_entity.created",
                "legal_entity",
                entity.id,
                after=model_snapshot(entity),
                request=request,
            )
        duplicate = db.scalar(
            select(Merchant.id).where(
                Merchant.legal_entity_id == entity.id,
                Merchant.name == row.merchant_name.strip(),
                Merchant.address == row.address.strip(),
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="该主体下已存在同名同址门店")

        merchant = Merchant(
            legal_entity_id=entity.id,
            name=row.merchant_name.strip(),
            industry=row.industry,
            phone=row.phone.strip(),
            address=row.address.strip(),
            business_hours=row.business_hours,
            contact_name=row.contact_name.strip(),
            scale=row.scale,
            employee_count=row.employee_count,
            store_area=row.store_area,
            network_environment=row.network_environment,
            bandwidth_mbps=row.bandwidth_mbps,
            needs=row.needs,
            is_demo=False,
            status="enabled",
        )
        db.add(merchant)
        db.flush()
        applicant.merchant_id = merchant.id
        for document in documents:
            document.legal_entity_id = entity.id
        row.status = "approved"
        add_audit(
            db,
            operator,
            "merchant.created_from_onboarding",
            "merchant",
            merchant.id,
            after=model_snapshot(merchant),
            request=request,
        )
    else:
        row.status = "needs_changes"
        row.truthfulness_confirmed = False
    row.review_note = payload.note.strip()
    row.reviewed_by = operator.id
    row.reviewed_at = utc_now()
    add_audit(
        db,
        operator,
        f"merchant_onboarding.{row.status}",
        "merchant_onboarding_application",
        row.id,
        before=before,
        after=model_snapshot(row),
        request=request,
    )
    if row.status == "approved":
        add_notification(
            db,
            recipient_user_id=applicant.id,
            notification_type="onboarding_approved",
            category="onboarding",
            title="店铺入驻申请已通过",
            message=f"{row.merchant_name}已通过审核，商户工作台现已开放",
            action="open_overview",
            target_type="merchant_onboarding_application",
            target_id=row.id,
            dedupe_key=f"onboarding:{row.id}:review:{row.reviewed_at.isoformat()}:approved",
            is_demo=False,
        )
    else:
        add_notification(
            db,
            recipient_user_id=applicant.id,
            notification_type="onboarding_needs_changes",
            category="onboarding",
            title="入驻资料需要补充",
            message=f"{row.merchant_name}的入驻资料需要补充，请查看管理员说明",
            action="open_onboarding_form",
            target_type="merchant_onboarding_application",
            target_id=row.id,
            dedupe_key=f"onboarding:{row.id}:review:{row.reviewed_at.isoformat()}:needs_changes",
            is_demo=False,
        )
    db.commit()
    db.refresh(row)
    return Envelope(
        message="入驻申请已通过" if row.status == "approved" else "已要求申请人补充资料",
        data=application_data(db, row, applicant),
    )
