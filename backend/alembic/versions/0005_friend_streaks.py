"""Add friend streak connections.

Revision ID: 0005_friend_streaks
Revises: 0004_subject_curriculum_metadata
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_friend_streaks"
down_revision = "0004_subject_curriculum_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "friend_streaks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_low_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_high_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_low_id", "user_high_id", name="uq_friend_streak_pair"),
    )
    op.create_index("ix_friend_streaks_user_low_id", "friend_streaks", ["user_low_id"])
    op.create_index("ix_friend_streaks_user_high_id", "friend_streaks", ["user_high_id"])


def downgrade() -> None:
    op.drop_index("ix_friend_streaks_user_high_id", table_name="friend_streaks")
    op.drop_index("ix_friend_streaks_user_low_id", table_name="friend_streaks")
    op.drop_table("friend_streaks")
