"""Add semester curriculum metadata to subjects.

Revision ID: 0004_subject_curriculum_metadata
Revises: 0003_coding_questions
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_subject_curriculum_metadata"
down_revision = "0003_coding_questions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subjects", sa.Column("curriculum_code", sa.String(length=20), nullable=True))
    op.add_column("subjects", sa.Column("semester", sa.Integer(), nullable=True))
    op.add_column("subjects", sa.Column("credits", sa.Integer(), nullable=True))
    op.create_index("ix_subjects_semester_order", "subjects", ["semester", "order"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_subjects_semester_order", table_name="subjects")
    op.drop_column("subjects", "credits")
    op.drop_column("subjects", "semester")
    op.drop_column("subjects", "curriculum_code")
