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


def upgrade() -> None:
    # The model metadata is intentionally created through SQLAlchemy's metadata
    # in the application startup for the first local foundation release.
    from app.core.database import Base
    from app.models import models  # noqa: F401
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.core.database import Base
    from app.models import models  # noqa: F401
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
