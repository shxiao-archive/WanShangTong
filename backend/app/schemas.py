import re
from datetime import date, datetime
from typing import Any, Generic, Literal, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T


def validate_password_strength(password: str) -> str:
    if not 8 <= len(password) <= 32:
        raise ValueError("密码长度必须为 8–32 位")
    categories = sum(
        (
            bool(re.search(r"[A-Za-z]", password)),
            bool(re.search(r"\d", password)),
            any(not char.isalnum() and not char.isspace() for char in password),
        )
    )
    if categories < 2:
        raise ValueError("密码必须至少包含数字、字母或符号中的两种")
    return password


class LoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=8, max_length=32)


class RegisterIn(BaseModel):
    account_type: Literal["merchant", "operator"]
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=32)
    display_name: str = Field(min_length=1, max_length=80)
    invitation_code: str | None = Field(default=None, max_length=100)
    accepted_rules: bool = False
    rules_version: str = Field(default="", max_length=40)
    accepted_privacy: bool = False
    privacy_version: str = Field(default="", max_length=40)
    merchant_name: str | None = Field(default=None, max_length=120)
    industry: str | None = Field(default=None, max_length=40)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_registration(self):
        validate_password_strength(self.password)
        if self.account_type == "operator":
            if not self.invitation_code or not self.invitation_code.strip():
                raise ValueError("管理人员注册必须填写邀请码")
        return self


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    merchant_id: int | None
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserStatusIn(BaseModel):
    is_active: bool


class TemporaryPasswordOut(BaseModel):
    user: UserOut
    temporary_password: str


class OperatorInviteOut(BaseModel):
    invitation_code: str
    expires_at: datetime


class ProductItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str = Field(min_length=1, max_length=80)
    category: str = Field(default="", max_length=50)
    price: float = Field(default=0, ge=0, le=99999999)
    image_id: int | None = None
    # Transitional read support for the one-time media backfill.
    image_url: str = Field(default="", max_length=500, exclude=True)


class MerchantBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    industry: str = Field(min_length=1, max_length=40)
    phone: str = Field(min_length=1, max_length=30)
    address: str = Field(min_length=1, max_length=255)
    business_hours: str = Field(default="09:00-21:00", max_length=80)
    contact_name: str = Field(default="", max_length=50)
    scale: str = Field(default="小微", max_length=20)
    employee_count: int = Field(default=3, ge=0, le=9999)
    store_area: int = Field(default=60, ge=0)
    network_environment: str = Field(default="普通宽带", max_length=40)
    bandwidth_mbps: int = Field(default=100, ge=0)
    tags: list[str] = Field(default_factory=list, max_length=30)
    needs: list[str] = Field(default_factory=list, max_length=30)
    image_url: str = Field(default="", max_length=500)
    products: list[ProductItem] = Field(default_factory=list, max_length=50)
    status: str = "enabled"
    is_demo: bool = False

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in {"enabled", "disabled"}:
            raise ValueError("状态只能是 enabled 或 disabled")
        return value


class MerchantCreate(MerchantBase):
    pass


class MerchantUpdate(MerchantBase):
    pass


class MerchantOut(MerchantBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MerchantOnboardingIn(BaseModel):
    merchant_name: str = Field(min_length=2, max_length=120)
    industry: str = Field(min_length=1, max_length=40)
    phone: str = Field(min_length=1, max_length=30)
    address: str = Field(min_length=1, max_length=255)
    business_hours: str = Field(default="09:00-21:00", max_length=80)
    contact_name: str = Field(min_length=1, max_length=50)
    scale: str = Field(default="小微", max_length=20)
    employee_count: int = Field(default=3, ge=0, le=9999)
    store_area: int = Field(default=60, ge=0, le=999999)
    network_environment: str = Field(default="普通宽带", max_length=40)
    bandwidth_mbps: int = Field(default=100, ge=0, le=100000)
    needs: list[str] = Field(default_factory=list, max_length=30)


USCC_CHARSET = "0123456789ABCDEFGHJKLMNPQRTUWXY"
USCC_WEIGHTS = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)


def normalize_and_validate_uscc(value: str) -> str:
    code = re.sub(r"\s+", "", value).upper()
    if len(code) != 18 or any(char not in USCC_CHARSET for char in code):
        raise ValueError("统一社会信用代码必须是有效的18位代码")
    check_index = (31 - sum(
        USCC_CHARSET.index(char) * weight
        for char, weight in zip(code[:17], USCC_WEIGHTS)
    ) % 31) % 31
    if code[-1] != USCC_CHARSET[check_index]:
        raise ValueError("统一社会信用代码校验位不正确")
    return code


def validate_uscc_subject_type(value: str, subject_type: str | None) -> str:
    code = normalize_and_validate_uscc(value)
    expected_prefix = {
        "enterprise": ("91", "企业"),
        "individual_business": ("92", "个体工商户"),
    }.get(subject_type or "")
    if expected_prefix and not code.startswith(expected_prefix[0]):
        raise ValueError(
            f"{expected_prefix[1]}的统一社会信用代码应以{expected_prefix[0]}开头"
        )
    return code


class AdditionalPermitIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    number: str = Field(default="", max_length=120)
    document_id: int = Field(gt=0)


class MerchantOnboardingDraftIn(BaseModel):
    subject_type: Literal["enterprise", "individual_business"] | None = None
    legal_name: str = Field(default="", max_length=160)
    unified_social_credit_code: str = Field(default="", max_length=30)
    legal_representative: str = Field(default="", max_length=80)
    registered_address: str = Field(default="", max_length=255)
    business_scope: str = Field(default="", max_length=3000)
    merchant_name: str = Field(default="", max_length=120)
    industry: Literal["餐饮", "零售", "生活服务", "住宿"] | None = None
    phone: str = Field(default="", max_length=30)
    address: str = Field(default="", max_length=255)
    business_hours: str = Field(default="09:00-21:00", max_length=80)
    contact_name: str = Field(default="", max_length=50)
    contact_relationship: Literal[
        "legal_representative", "business_operator", "store_manager", "authorized_agent"
    ] | None = None
    authorization_confirmed: bool = False
    scale: Literal["小微", "中小", "中型"] = "小微"
    employee_count: int = Field(default=3, ge=0, le=9999)
    store_area: int = Field(default=60, ge=0, le=999999)
    network_environment: str = Field(default="普通宽带", max_length=40)
    bandwidth_mbps: int = Field(default=100, ge=0, le=100000)
    needs: list[str] = Field(default_factory=list, max_length=30)
    retail_food_related: bool = False
    retail_food_credential_type: Literal[
        "food_business_license", "prepackaged_food_filing"
    ] | None = None
    other_permit_required: bool = False
    other_permit_name: str = Field(default="", max_length=120)
    other_permit_number: str = Field(default="", max_length=120)
    additional_permits: list[AdditionalPermitIn] = Field(default_factory=list, max_length=10)
    current_step: int = Field(default=0, ge=0, le=4)

    @field_validator("unified_social_credit_code")
    @classmethod
    def normalize_uscc_if_present(cls, value: str) -> str:
        code = re.sub(r"\s+", "", value).upper()
        if code and len(code) > 18:
            raise ValueError("统一社会信用代码不能超过18位")
        return code


class MerchantOnboardingSubmitIn(BaseModel):
    truthfulness_confirmed: bool
    accepted_rules: bool
    rules_version: str = Field(max_length=40)
    accepted_privacy: bool
    privacy_version: str = Field(max_length=40)


class CredentialDocumentOut(BaseModel):
    id: int
    document_type: str
    document_number: str
    original_name: str
    mime_type: str
    file_size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MerchantOnboardingReviewIn(BaseModel):
    action: Literal["approve", "request_changes"]
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_review(self):
        if self.action == "request_changes" and not self.note.strip():
            raise ValueError("要求补充资料时必须填写说明")
        return self


class MerchantOnboardingOut(MerchantOnboardingDraftIn):
    id: int
    user_id: int
    username: str = ""
    display_name: str = ""
    status: Literal["draft", "pending", "approved", "needs_changes"]
    review_note: str
    reviewed_by: int | None
    reviewed_at: datetime | None
    submitted_at: datetime | None
    truthfulness_confirmed: bool
    rules_version: str | None
    privacy_version: str | None
    documents: list[CredentialDocumentOut] = Field(default_factory=list)
    existing_entity: dict | None = None
    duplicate_store: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BusinessDataIn(BaseModel):
    business_date: date
    visitors: int = Field(ge=0)
    orders: int = Field(ge=0)
    revenue: float = Field(ge=0, le=999999999)
    rating: float = Field(default=5, ge=0, le=5)
    dine_in_orders: int = Field(default=0, ge=0)
    delivery_orders: int = Field(default=0, ge=0)
    group_buy_orders: int = Field(default=0, ge=0)
    other_orders: int = Field(default=0, ge=0)
    peak_hour: int = Field(default=12, ge=0, le=23)

    @model_validator(mode="after")
    def valid_business_data(self):
        if self.business_date > date.today():
            raise ValueError("经营日期不能晚于今天")
        source_total = (
            self.dine_in_orders
            + self.delivery_orders
            + self.group_buy_orders
            + self.other_orders
        )
        if source_total != self.orders:
            raise ValueError("到店、外卖、团购和其他订单之和必须等于总订单")
        self.revenue = round(self.revenue, 2)
        return self


class BusinessDataOut(BusinessDataIn):
    id: int
    merchant_id: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: str
    description: str
    price: float = Field(ge=0)
    unit: str = "元/月"
    bandwidth_mbps: int | None = Field(default=None, ge=0)
    target_industries: list[str] = Field(default_factory=list)
    matched_needs: list[str] = Field(default_factory=list)
    included_services: list[str] = Field(default_factory=list)
    is_universal: bool = False
    status: str = "enabled"


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(ResourceBase):
    pass


class ResourceOut(ResourceBase):
    id: int
    subscription_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StatusIn(BaseModel):
    status: str


class MediaOut(BaseModel):
    id: int
    merchant_id: int
    mime_type: str
    file_size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


APPLICATION_STATUSES = {"pending", "processing", "completed", "canceled"}


class ApplicationCreate(BaseModel):
    merchant_id: int
    resource_id: int
    contact_name: str = Field(min_length=1, max_length=80)
    contact_phone: str = Field(min_length=5, max_length=30)
    merchant_note: str = Field(default="", max_length=500)


class ApplicationStatusIn(BaseModel):
    status: str
    note: str = Field(default="", max_length=1000)

    @field_validator("status")
    @classmethod
    def valid_application_status(cls, value: str) -> str:
        if value not in APPLICATION_STATUSES:
            raise ValueError("申请状态不正确")
        return value


class ApplicationNoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=1000)


class ApplicationEventOut(BaseModel):
    id: int
    actor_user_id: int
    event_type: str
    from_status: str | None
    to_status: str | None
    note: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationOut(BaseModel):
    id: int
    merchant_id: int
    resource_id: int
    contact_name: str
    contact_phone: str
    merchant_note: str
    recommendation_score: int
    recommendation_reasons: list[str]
    resource_snapshot: dict[str, Any]
    status: str
    is_demo: bool
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    events: list[ApplicationEventOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
