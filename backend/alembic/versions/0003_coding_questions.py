"""Add safe interactive coding-question metadata.

Revision ID: 0003_coding_questions
Revises: 0002_performance_indexes
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_coding_questions"
down_revision = "0002_performance_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("coding_language", sa.String(length=50), nullable=True))
    op.add_column("questions", sa.Column("starter_code", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("test_cases", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("questions", "test_cases")
    op.drop_column("questions", "starter_code")
    op.drop_column("questions", "coding_language")
