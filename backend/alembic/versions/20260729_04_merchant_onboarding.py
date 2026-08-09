"""merchant onboarding applications

Revision ID: 20260729_04
Revises: 20260729_03
Create Date: 2026-07-29
"""

import sqlalchemy as sa
from alembic import op

revision = "20260729_04"
down_revision = "20260729_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "merchant_onboarding_applications" in sa.inspect(bind).get_table_names():
        # The foundation migration creates all tables from current metadata
        # when upgrading a completely empty database.
        return

    op.create_table(
        "merchant_onboarding_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("merchant_name", sa.String(length=120), nullable=False),
        sa.Column("industry", sa.String(length=40), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("business_hours", sa.String(length=80), nullable=False),
        sa.Column("contact_name", sa.String(length=50), nullable=False),
        sa.Column("scale", sa.String(length=20), nullable=False),
        sa.Column("employee_count", sa.Integer(), nullable=False),
        sa.Column("store_area", sa.Integer(), nullable=False),
        sa.Column("network_environment", sa.String(length=40), nullable=False),
        sa.Column("bandwidth_mbps", sa.Integer(), nullable=False),
        sa.Column("needs", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("review_note", sa.String(length=500), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_merchant_onboarding_user_id"),
    )
    op.create_index(
        op.f("ix_merchant_onboarding_applications_status"),
        "merchant_onboarding_applications",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_merchant_onboarding_applications_user_id"),
        "merchant_onboarding_applications",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "merchant_onboarding_applications" not in sa.inspect(bind).get_table_names():
        return

    op.drop_index(
        op.f("ix_merchant_onboarding_applications_user_id"),
        table_name="merchant_onboarding_applications",
    )
    op.drop_index(
        op.f("ix_merchant_onboarding_applications_status"),
        table_name="merchant_onboarding_applications",
    )
    op.drop_table("merchant_onboarding_applications")
