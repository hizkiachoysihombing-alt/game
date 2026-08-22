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
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("subjects")}
    if "curriculum_code" not in existing:
        op.add_column("subjects", sa.Column("curriculum_code", sa.String(length=20), nullable=True))
    if "semester" not in existing:
        op.add_column("subjects", sa.Column("semester", sa.Integer(), nullable=True))
    if "credits" not in existing:
        op.add_column("subjects", sa.Column("credits", sa.Integer(), nullable=True))
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("subjects")}
    if "ix_subjects_semester_order" not in indexes:
        op.create_index("ix_subjects_semester_order", "subjects", ["semester", "order"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("subjects")}
    if "ix_subjects_semester_order" in indexes:
        op.drop_index("ix_subjects_semester_order", table_name="subjects")
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("subjects")}
    if "credits" in existing:
        op.drop_column("subjects", "credits")
    if "semester" in existing:
        op.drop_column("subjects", "semester")
    if "curriculum_code" in existing:
        op.drop_column("subjects", "curriculum_code")
