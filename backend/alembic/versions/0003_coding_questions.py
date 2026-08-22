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
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("questions")}
    if "coding_language" not in existing:
        op.add_column("questions", sa.Column("coding_language", sa.String(length=50), nullable=True))
    if "starter_code" not in existing:
        op.add_column("questions", sa.Column("starter_code", sa.Text(), nullable=True))
    if "test_cases" not in existing:
        op.add_column("questions", sa.Column("test_cases", sa.JSON(), nullable=True))


def downgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("questions")}
    if "test_cases" in existing:
        op.drop_column("questions", "test_cases")
    if "starter_code" in existing:
        op.drop_column("questions", "starter_code")
    if "coding_language" in existing:
        op.drop_column("questions", "coding_language")
