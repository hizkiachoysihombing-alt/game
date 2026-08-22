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
    inspector = sa.inspect(op.get_bind())
    if "friend_streaks" not in inspector.get_table_names():
        op.create_table(
            "friend_streaks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_low_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_high_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_low_id", "user_high_id", name="uq_friend_streak_pair"),
        )
    indexes = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("friend_streaks")
    }
    if "ix_friend_streaks_user_low_id" not in indexes:
        op.create_index("ix_friend_streaks_user_low_id", "friend_streaks", ["user_low_id"])
    if "ix_friend_streaks_user_high_id" not in indexes:
        op.create_index("ix_friend_streaks_user_high_id", "friend_streaks", ["user_high_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "friend_streaks" not in inspector.get_table_names():
        return
    indexes = {index["name"] for index in inspector.get_indexes("friend_streaks")}
    if "ix_friend_streaks_user_high_id" in indexes:
        op.drop_index("ix_friend_streaks_user_high_id", table_name="friend_streaks")
    if "ix_friend_streaks_user_low_id" in indexes:
        op.drop_index("ix_friend_streaks_user_low_id", table_name="friend_streaks")
    op.drop_table("friend_streaks")
