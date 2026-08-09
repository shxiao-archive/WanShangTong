"""operator invitation codes

Revision ID: 20260729_02
Revises: 20260728_01
Create Date: 2026-07-29
"""

import sqlalchemy as sa
from alembic import op

revision = "20260729_02"
down_revision = "20260728_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "operator_invites" in inspector.get_table_names():
        return
    op.create_table(
        "operator_invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("used_by", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["used_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_operator_invites_code_hash"),
        "operator_invites",
        ["code_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_operator_invites_created_by"),
        "operator_invites",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operator_invites_expires_at"),
        "operator_invites",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_operator_invites_expires_at"), table_name="operator_invites")
    op.drop_index(op.f("ix_operator_invites_created_by"), table_name="operator_invites")
    op.drop_index(op.f("ix_operator_invites_code_hash"), table_name="operator_invites")
    op.drop_table("operator_invites")
