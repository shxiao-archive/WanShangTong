"""notification and todo inbox

Revision ID: 20260812_06
Revises: 20260729_05
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from alembic import op

revision = "20260812_06"
down_revision = "20260729_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "notifications" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("message", sa.String(length=300), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column(
            "is_demo", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("dedupe_key", sa.String(length=180), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recipient_user_id",
            "dedupe_key",
            name="uq_notifications_recipient_dedupe",
        ),
    )
    op.create_index(
        "ix_notifications_recipient_read_created",
        "notifications",
        ["recipient_user_id", "read_at", "created_at"],
    )
    op.create_index(
        "ix_notifications_recipient_id",
        "notifications",
        ["recipient_user_id", "id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "notifications" not in sa.inspect(bind).get_table_names():
        return
    op.drop_index("ix_notifications_recipient_id", table_name="notifications")
    op.drop_index(
        "ix_notifications_recipient_read_created", table_name="notifications"
    )
    op.drop_table("notifications")
