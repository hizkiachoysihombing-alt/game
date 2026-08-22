"""Create the initial ElectroQuest schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


# This migration originally called ``Base.metadata.create_all`` without a table
# allow-list.  That makes a fresh install depend on whichever models happen to
# exist years later: newer columns/tables are created at revision 0001 and the
# revision that owns them then fails with a duplicate-object error.  Keep the
# historical baseline explicit while retaining the original metadata-driven DDL.
BASELINE_TABLES = (
    "users",
    "subjects",
    "learning_paths",
    "courses",
    "modules",
    "lessons",
    "enrollments",
    "lesson_progress",
    "topics",
    "concept_tags",
    "questions",
    "question_banks",
    "question_answers",
    "quizzes",
    "misconceptions",
    "problem_submissions",
    "quiz_submissions",
    "gamification_profiles",
    "xp_transactions",
    "achievements",
    "user_achievements",
    "quests",
    "user_quests",
    "leaderboards",
    "mastery_records",
    "reasoning_diagnoses",
    "reasoning_errors",
    "subscriptions",
    "subscription_prices",
    "payment_transactions",
    "billing_events",
    "refunds",
    "subscription_entitlements",
    "usage_quotas",
    "usage_ledger",
    "question_concepts",
    "quiz_questions",
    "learning_path_courses",
    "learning_path_prerequisites",
)

# These indexes are owned by revisions 0002 and 0004.  They are now declared in
# SQLAlchemy metadata for drift detection, so omit them while revision 0001 runs.
DEFERRED_INDEXES = {
    "ix_leaderboards_period_category_score",
    "ix_problem_submissions_user_submitted",
    "ix_subjects_semester_order",
}


def _baseline_metadata():
    from app.core.database import Base
    from app.models import models  # noqa: F401

    return Base, [Base.metadata.tables[name] for name in BASELINE_TABLES]


def _without_deferred_indexes(tables):
    removed = []
    for table in tables:
        for index in tuple(table.indexes):
            if index.name in DEFERRED_INDEXES:
                table.indexes.remove(index)
                removed.append((table, index))
    return removed


def _restore_indexes(removed) -> None:
    for table, index in removed:
        table.indexes.add(index)


def upgrade() -> None:
    Base, tables = _baseline_metadata()
    bind = op.get_bind()
    removed = _without_deferred_indexes(tables)
    try:
        Base.metadata.create_all(bind=bind, tables=tables)
    finally:
        _restore_indexes(removed)


def downgrade() -> None:
    Base, tables = _baseline_metadata()
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, tables=tables)
