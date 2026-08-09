"""remove contacted application status

Revision ID: 20260729_03
Revises: 20260729_02
Create Date: 2026-07-29
"""

from alembic import op

revision = "20260729_03"
down_revision = "20260729_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE service_applications "
        "SET status = 'processing' "
        "WHERE status = 'contacted'"
    )


def downgrade() -> None:
    # A processing row cannot be reliably distinguished from a formerly
    # contacted row, so the data migration is intentionally irreversible.
    pass
