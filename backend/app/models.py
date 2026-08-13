from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    """Return a UTC value compatible with MySQL's timezone-naive DATETIME."""
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("merchant_id", name="uq_users_merchant_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(20), index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class OperatorInvite(Base):
    __tablename__ = "operator_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    used_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)
    legal_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("legal_entities.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), index=True)
    industry: Mapped[str] = mapped_column(String(40), index=True)
    phone: Mapped[str] = mapped_column(String(30))
    address: Mapped[str] = mapped_column(String(255))
    business_hours: Mapped[str] = mapped_column(String(80), default="09:00-21:00")
    contact_name: Mapped[str] = mapped_column(String(50), default="")
    scale: Mapped[str] = mapped_column(String(20), default="小微")
    employee_count: Mapped[int] = mapped_column(Integer, default=3)
    store_area: Mapped[int] = mapped_column(Integer, default=60)
    network_environment: Mapped[str] = mapped_column(String(40), default="普通宽带")
    bandwidth_mbps: Mapped[int] = mapped_column(Integer, default=100)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    needs: Mapped[list] = mapped_column(JSON, default=list)
    image_url: Mapped[str] = mapped_column(String(500), default="")
    products: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="enabled", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    business_data: Mapped[list["BusinessData"]] = relationship(
        cascade="all, delete-orphan", back_populates="merchant"
    )


class MerchantOnboardingApplication(Base):
    __tablename__ = "merchant_onboarding_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    subject_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    legal_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    unified_social_credit_code: Mapped[str | None] = mapped_column(
        String(18), nullable=True, index=True
    )
    legal_representative: Mapped[str | None] = mapped_column(String(80), nullable=True)
    registered_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant_name: Mapped[str] = mapped_column(String(120))
    industry: Mapped[str] = mapped_column(String(40))
    phone: Mapped[str] = mapped_column(String(30))
    address: Mapped[str] = mapped_column(String(255))
    business_hours: Mapped[str] = mapped_column(String(80), default="09:00-21:00")
    contact_name: Mapped[str] = mapped_column(String(50), default="")
    contact_relationship: Mapped[str | None] = mapped_column(String(30), nullable=True)
    authorization_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    scale: Mapped[str] = mapped_column(String(20), default="小微")
    employee_count: Mapped[int] = mapped_column(Integer, default=3)
    store_area: Mapped[int] = mapped_column(Integer, default=60)
    network_environment: Mapped[str] = mapped_column(String(40), default="普通宽带")
    bandwidth_mbps: Mapped[int] = mapped_column(Integer, default=100)
    needs: Mapped[list] = mapped_column(JSON, default=list)
    retail_food_related: Mapped[bool] = mapped_column(Boolean, default=False)
    retail_food_credential_type: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    other_permit_required: Mapped[bool] = mapped_column(Boolean, default=False)
    other_permit_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    other_permit_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    additional_permits: Mapped[list] = mapped_column(JSON, default=list)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    rules_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    privacy_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    truthfulness_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    review_note: Mapped[str] = mapped_column(String(500), default="")
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )


class LegalEntity(Base):
    __tablename__ = "legal_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(30))
    legal_name: Mapped[str] = mapped_column(String(160), index=True)
    unified_social_credit_code: Mapped[str] = mapped_column(
        String(18), unique=True, index=True
    )
    legal_representative: Mapped[str] = mapped_column(String(80))
    registered_address: Mapped[str] = mapped_column(String(255))
    business_scope: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="verified", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )


class CredentialDocument(Base):
    __tablename__ = "credential_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("merchant_onboarding_applications.id"), index=True
    )
    legal_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("legal_entities.id"), nullable=True, index=True
    )
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(50), index=True)
    document_number: Mapped[str] = mapped_column(String(120), default="")
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(80))
    file_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class UserConsent(Base):
    __tablename__ = "user_consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchant_onboarding_applications.id"), nullable=True, index=True
    )
    agreement_type: Mapped[str] = mapped_column(String(40), index=True)
    version: Mapped[str] = mapped_column(String(40))
    ip_hash: Mapped[str] = mapped_column(String(64), default="")
    user_agent_hash: Mapped[str] = mapped_column(String(64), default="")
    accepted_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class BusinessData(Base):
    __tablename__ = "business_data"
    __table_args__ = (
        UniqueConstraint("merchant_id", "business_date", name="uq_business_data_merchant_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    business_date: Mapped[date] = mapped_column(Date, index=True)
    visitors: Mapped[int] = mapped_column(Integer, default=0)
    orders: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0)
    rating: Mapped[float] = mapped_column(Float, default=5)
    dine_in_orders: Mapped[int] = mapped_column(Integer, default=0)
    delivery_orders: Mapped[int] = mapped_column(Integer, default=0)
    group_buy_orders: Mapped[int] = mapped_column(Integer, default=0)
    other_orders: Mapped[int] = mapped_column(Integer, default=0)
    peak_hour: Mapped[int] = mapped_column(Integer, default=12)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    merchant: Mapped[Merchant] = relationship(back_populates="business_data")


class ServiceResource(Base):
    __tablename__ = "service_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str] = mapped_column(String(500))
    price: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(30), default="元/月")
    bandwidth_mbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_industries: Mapped[list] = mapped_column(JSON, default=list)
    matched_needs: Mapped[list] = mapped_column(JSON, default=list)
    included_services: Mapped[list] = mapped_column(JSON, default=list)
    is_universal: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="enabled", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    original_name: Mapped[str] = mapped_column(String(255), default="")
    mime_type: Mapped[str] = mapped_column(String(80))
    file_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ServiceApplication(Base):
    __tablename__ = "service_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("service_resources.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    contact_name: Mapped[str] = mapped_column(String(80))
    contact_phone: Mapped[str] = mapped_column(String(30))
    merchant_note: Mapped[str] = mapped_column(String(500), default="")
    recommendation_score: Mapped[int] = mapped_column(Integer, default=0)
    recommendation_reasons: Mapped[list] = mapped_column(JSON, default=list)
    resource_snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    active_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    events: Mapped[list["ApplicationEvent"]] = relationship(
        cascade="all, delete-orphan", back_populates="application", order_by="ApplicationEvent.id"
    )


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("service_applications.id"), index=True
    )
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(30))
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    application: Mapped[ServiceApplication] = relationship(back_populates="events")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "recipient_user_id", "dedupe_key", name="uq_notifications_recipient_dedupe"
        ),
        Index(
            "ix_notifications_recipient_read_created",
            "recipient_user_id",
            "read_at",
            "created_at",
        ),
        Index("ix_notifications_recipient_id", "recipient_user_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(String(300))
    action: Mapped[str] = mapped_column(String(50))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    dedupe_key: Mapped[str] = mapped_column(String(180))
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(50), index=True)
    target_id: Mapped[str] = mapped_column(String(80), index=True)
    before_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str] = mapped_column(String(80), default="")
    ip_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
