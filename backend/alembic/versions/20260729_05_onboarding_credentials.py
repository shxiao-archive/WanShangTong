"""onboarding credentials and legal entities

Revision ID: 20260729_05
Revises: 20260729_04
Create Date: 2026-07-29
"""

import sqlalchemy as sa
from alembic import op

revision = "20260729_05"
down_revision = "20260729_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "legal_entities" not in tables:
        op.create_table(
            "legal_entities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("subject_type", sa.String(length=30), nullable=False),
            sa.Column("legal_name", sa.String(length=160), nullable=False),
            sa.Column(
                "unified_social_credit_code", sa.String(length=18), nullable=False
            ),
            sa.Column("legal_representative", sa.String(length=80), nullable=False),
            sa.Column("registered_address", sa.String(length=255), nullable=False),
            sa.Column("business_scope", sa.Text(), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="verified",
            ),
            sa.Column(
                "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
            ),
            sa.Column(
                "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "unified_social_credit_code",
                name="uq_legal_entities_unified_social_credit_code",
            ),
        )
        op.create_index(
            "ix_legal_entities_legal_name", "legal_entities", ["legal_name"]
        )
        op.create_index(
            "ix_legal_entities_unified_social_credit_code",
            "legal_entities",
            ["unified_social_credit_code"],
            unique=True,
        )
        op.create_index("ix_legal_entities_status", "legal_entities", ["status"])

    merchant_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("merchants")
    }
    if "legal_entity_id" not in merchant_columns:
        op.add_column(
            "merchants", sa.Column("legal_entity_id", sa.Integer(), nullable=True)
        )
        op.create_index(
            "ix_merchants_legal_entity_id",
            "merchants",
            ["legal_entity_id"],
            unique=False,
        )
        if bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_merchants_legal_entity_id",
                "merchants",
                "legal_entities",
                ["legal_entity_id"],
                ["id"],
            )

    onboarding_columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns(
            "merchant_onboarding_applications"
        )
    }
    additions = [
        ("subject_type", sa.Column("subject_type", sa.String(30), nullable=True)),
        ("legal_name", sa.Column("legal_name", sa.String(160), nullable=True)),
        (
            "unified_social_credit_code",
            sa.Column("unified_social_credit_code", sa.String(18), nullable=True),
        ),
        (
            "legal_representative",
            sa.Column("legal_representative", sa.String(80), nullable=True),
        ),
        (
            "registered_address",
            sa.Column("registered_address", sa.String(255), nullable=True),
        ),
        ("business_scope", sa.Column("business_scope", sa.Text(), nullable=True)),
        (
            "contact_relationship",
            sa.Column("contact_relationship", sa.String(30), nullable=True),
        ),
        (
            "authorization_confirmed",
            sa.Column(
                "authorization_confirmed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        ),
        (
            "retail_food_related",
            sa.Column(
                "retail_food_related",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        ),
        (
            "retail_food_credential_type",
            sa.Column("retail_food_credential_type", sa.String(40), nullable=True),
        ),
        (
            "other_permit_required",
            sa.Column(
                "other_permit_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        ),
        (
            "other_permit_name",
            sa.Column("other_permit_name", sa.String(120), nullable=True),
        ),
        (
            "other_permit_number",
            sa.Column("other_permit_number", sa.String(120), nullable=True),
        ),
        (
            "additional_permits",
            sa.Column("additional_permits", sa.JSON(), nullable=True),
        ),
        (
            "current_step",
            sa.Column(
                "current_step", sa.Integer(), nullable=False, server_default="0"
            ),
        ),
        ("rules_version", sa.Column("rules_version", sa.String(40), nullable=True)),
        (
            "privacy_version",
            sa.Column("privacy_version", sa.String(40), nullable=True),
        ),
        (
            "truthfulness_confirmed",
            sa.Column(
                "truthfulness_confirmed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        ),
        ("submitted_at", sa.Column("submitted_at", sa.DateTime(), nullable=True)),
    ]
    for name, column in additions:
        if name not in onboarding_columns:
            op.add_column("merchant_onboarding_applications", column)
    refreshed_columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns(
            "merchant_onboarding_applications"
        )
    }
    if "unified_social_credit_code" in refreshed_columns:
        index_names = {
            item["name"]
            for item in sa.inspect(bind).get_indexes(
                "merchant_onboarding_applications"
            )
        }
        if "ix_merchant_onboarding_applications_unified_social_credit_code" not in index_names:
            op.create_index(
                "ix_merchant_onboarding_applications_unified_social_credit_code",
                "merchant_onboarding_applications",
                ["unified_social_credit_code"],
            )
    op.execute(
        "UPDATE merchant_onboarding_applications "
        "SET status = 'needs_changes', "
        "review_note = CASE WHEN review_note = '' "
        "THEN '请补充营业执照及主体资质材料' ELSE review_note END "
        "WHERE status IN ('pending', 'rejected')"
    )

    tables = set(sa.inspect(bind).get_table_names())
    if "credential_documents" not in tables:
        op.create_table(
            "credential_documents",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("application_id", sa.Integer(), nullable=False),
            sa.Column("legal_entity_id", sa.Integer(), nullable=True),
            sa.Column("uploaded_by", sa.Integer(), nullable=False),
            sa.Column("document_type", sa.String(50), nullable=False),
            sa.Column(
                "document_number",
                sa.String(120),
                nullable=False,
                server_default="",
            ),
            sa.Column("storage_key", sa.String(255), nullable=False),
            sa.Column("original_name", sa.String(255), nullable=False),
            sa.Column("mime_type", sa.String(80), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
            ),
            sa.ForeignKeyConstraint(
                ["application_id"], ["merchant_onboarding_applications.id"]
            ),
            sa.ForeignKeyConstraint(["legal_entity_id"], ["legal_entities.id"]),
            sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("storage_key"),
        )
        for column in (
            "application_id",
            "legal_entity_id",
            "uploaded_by",
            "document_type",
            "sha256",
            "deleted_at",
        ):
            op.create_index(
                f"ix_credential_documents_{column}",
                "credential_documents",
                [column],
            )

    if "user_consents" not in tables:
        op.create_table(
            "user_consents",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("application_id", sa.Integer(), nullable=True),
            sa.Column("agreement_type", sa.String(40), nullable=False),
            sa.Column("version", sa.String(40), nullable=False),
            sa.Column("ip_hash", sa.String(64), nullable=False, server_default=""),
            sa.Column(
                "user_agent_hash", sa.String(64), nullable=False, server_default=""
            ),
            sa.Column(
                "accepted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
            ),
            sa.ForeignKeyConstraint(["application_id"], ["merchant_onboarding_applications.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ("user_id", "application_id", "agreement_type"):
            op.create_index(
                f"ix_user_consents_{column}", "user_consents", [column]
            )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "user_consents" in tables:
        op.drop_table("user_consents")
    if "credential_documents" in tables:
        op.drop_table("credential_documents")

    onboarding_columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns(
            "merchant_onboarding_applications"
        )
    }
    for name in (
        "submitted_at",
        "truthfulness_confirmed",
        "privacy_version",
        "rules_version",
        "current_step",
        "additional_permits",
        "other_permit_number",
        "other_permit_name",
        "other_permit_required",
        "retail_food_credential_type",
        "retail_food_related",
        "authorization_confirmed",
        "contact_relationship",
        "business_scope",
        "registered_address",
        "legal_representative",
        "unified_social_credit_code",
        "legal_name",
        "subject_type",
    ):
        if name in onboarding_columns:
            op.drop_column("merchant_onboarding_applications", name)

    merchant_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("merchants")
    }
    if "legal_entity_id" in merchant_columns:
        op.drop_constraint(
            "fk_merchants_legal_entity_id", "merchants", type_="foreignkey"
        )
        op.drop_index("ix_merchants_legal_entity_id", table_name="merchants")
        op.drop_column("merchants", "legal_entity_id")
    if "legal_entities" in tables:
        op.drop_table("legal_entities")
