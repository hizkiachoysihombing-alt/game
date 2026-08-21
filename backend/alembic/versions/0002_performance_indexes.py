"""Add indexes for weekly ranking and adaptive history queries.

Revision ID: 0002_performance_indexes
Revises: 0001_initial_schema
"""
from alembic import op

revision = "0002_performance_indexes"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_leaderboards_period_category_score", "leaderboards", ["period", "category", "score"], unique=False)
    op.create_index("ix_problem_submissions_user_submitted", "problem_submissions", ["user_id", "submitted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_problem_submissions_user_submitted", table_name="problem_submissions")
    op.drop_index("ix_leaderboards_period_category_score", table_name="leaderboards")
