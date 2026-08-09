"""trial foundation

Revision ID: 20260728_01
Revises:
Create Date: 2026-07-28
"""
import json
from datetime import date, datetime

import sqlalchemy as sa
from alembic import op

from app.models import Base

revision = "20260728_01"
down_revision = None
branch_labels = None
depends_on = None


def json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        Base.metadata.create_all(bind)
        return

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    user_additions = [
        ("must_change_password", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("token_version", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")),
        ("failed_login_count", sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0")),
        ("locked_until", sa.Column("locked_until", sa.DateTime(), nullable=True)),
        ("last_login_at", sa.Column("last_login_at", sa.DateTime(), nullable=True)),
        # SQLite cannot add a column with CURRENT_TIMESTAMP as a non-constant
        # default. Application writes always populate this field, while MySQL
        # production databases that already ran the migration are unaffected.
        ("updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True)),
    ]
    for name, column in user_additions:
        if name not in user_columns:
            op.add_column("users", column)

    merchant_columns = {column["name"] for column in inspector.get_columns("merchants")}
    if "is_demo" not in merchant_columns:
        op.add_column(
            "merchants",
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        # IDs 1-6 are the original seeded demonstration merchants. Merchants
        # created after the seed must remain real trial data.
        op.execute(sa.text("UPDATE merchants SET is_demo = 1 WHERE id BETWEEN 1 AND 6"))
        op.create_index("ix_merchants_is_demo", "merchants", ["is_demo"])

    business_columns = {column["name"] for column in inspector.get_columns("business_data")}
    if "is_deleted" not in business_columns:
        op.add_column(
            "business_data",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.add_column("business_data", sa.Column("deleted_at", sa.DateTime(), nullable=True))
        op.add_column("business_data", sa.Column("deleted_by", sa.Integer(), nullable=True))
        op.create_index("ix_business_data_is_deleted", "business_data", ["is_deleted"])
        if bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_business_data_deleted_by_users",
                "business_data",
                "users",
                ["deleted_by"],
                ["id"],
            )

    for table_name in (
        "audit_logs",
        "media_assets",
        "service_applications",
        "application_events",
    ):
        Base.metadata.tables[table_name].create(bind, checkfirst=True)

    duplicate_groups = bind.execute(
        sa.text(
            "SELECT merchant_id, business_date, COUNT(*) AS amount "
            "FROM business_data GROUP BY merchant_id, business_date HAVING COUNT(*) > 1"
        )
    ).mappings().all()
    audit_insert = sa.text(
        "INSERT INTO audit_logs "
        "(actor_user_id, action, target_type, target_id, before_data, request_id, ip_hash, created_at) "
        "VALUES (NULL, 'migration.deduplicated', 'business_data', :target_id, :before_data, '', '', :created_at)"
    ).bindparams(sa.bindparam("before_data", type_=sa.JSON()))
    for group in duplicate_groups:
        rows = bind.execute(
            sa.text(
                "SELECT * FROM business_data WHERE merchant_id=:merchant_id "
                "AND business_date=:business_date ORDER BY updated_at DESC, id DESC"
            ),
            group,
        ).mappings().all()
        for duplicate in rows[1:]:
            bind.execute(
                audit_insert,
                {
                    "target_id": str(duplicate["id"]),
                    "before_data": json.loads(
                        json.dumps(
                            dict(duplicate), ensure_ascii=False, default=json_default
                        )
                    ),
                    "created_at": datetime.utcnow(),
                },
            )
            bind.execute(
                sa.text("DELETE FROM business_data WHERE id=:id"),
                {"id": duplicate["id"]},
            )

    unique_names = {item.get("name") for item in inspector.get_unique_constraints("users")}
    if "uq_users_merchant_id" not in unique_names:
        if bind.dialect.name == "sqlite":
            op.create_index(
                "uq_users_merchant_id", "users", ["merchant_id"], unique=True
            )
        else:
            op.create_unique_constraint(
                "uq_users_merchant_id", "users", ["merchant_id"]
            )
    business_unique_names = {
        item.get("name") for item in inspector.get_unique_constraints("business_data")
    }
    if "uq_business_data_merchant_date" not in business_unique_names:
        if bind.dialect.name == "sqlite":
            op.create_index(
                "uq_business_data_merchant_date",
                "business_data",
                ["merchant_id", "business_date"],
                unique=True,
            )
        else:
            op.create_unique_constraint(
                "uq_business_data_merchant_date",
                "business_data",
                ["merchant_id", "business_date"],
            )


def downgrade() -> None:
    op.drop_constraint("uq_business_data_merchant_date", "business_data", type_="unique")
    op.drop_constraint("uq_users_merchant_id", "users", type_="unique")
    for table_name in (
        "application_events",
        "service_applications",
        "media_assets",
        "audit_logs",
    ):
        op.drop_table(table_name)
    op.drop_constraint("fk_business_data_deleted_by_users", "business_data", type_="foreignkey")
    op.drop_index("ix_business_data_is_deleted", table_name="business_data")
    for column in ("deleted_by", "deleted_at", "is_deleted"):
        op.drop_column("business_data", column)
    op.drop_index("ix_merchants_is_demo", table_name="merchants")
    op.drop_column("merchants", "is_demo")
    for column in (
        "updated_at",
        "last_login_at",
        "locked_until",
        "failed_login_count",
        "token_version",
        "must_change_password",
    ):
        op.drop_column("users", column)
