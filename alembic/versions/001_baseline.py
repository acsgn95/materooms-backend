"""baseline — represents DB state created via create_all

Revision ID: baseline_001
Revises:
Create Date: 2026-07-25
"""

revision = 'baseline_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables were created manually via Base.metadata.create_all.
    # This baseline is stamped on existing deployments so migration 002 can run.
    pass


def downgrade() -> None:
    pass
