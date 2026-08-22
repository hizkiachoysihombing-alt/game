"""Add managed source library, reading history, and question provenance.

Revision ID: 0006_source_learning_workflow
Revises: 0005_friend_streaks
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_source_learning_workflow"
down_revision = "0005_friend_streaks"
branch_labels = None
depends_on = None


QUESTION_COLUMNS = {
    "workflow_status": sa.Column(
        "workflow_status", sa.String(length=30), nullable=False, server_default="draft"
    ),
    "requires_citation": sa.Column(
        "requires_citation", sa.Boolean(), nullable=False, server_default=sa.true()
    ),
    "generated_by_ai": sa.Column(
        "generated_by_ai", sa.Boolean(), nullable=False, server_default=sa.false()
    ),
    "reviewed_by_id": sa.Column(
        "reviewed_by_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    "reviewed_at": sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    "review_notes": sa.Column("review_notes", sa.Text(), nullable=True),
    "published_at": sa.Column("published_at", sa.DateTime(), nullable=True),
    "generation_metadata": sa.Column("generation_metadata", sa.JSON(), nullable=True),
}


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    return {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes(table_name)
        if index.get("name")
    }


def _create_index_if_missing(
    name: str, table_name: str, columns: list[str], *, unique: bool = False
) -> None:
    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns, unique=unique)


def _add_question_workflow_columns() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("questions")}
    for name, column in QUESTION_COLUMNS.items():
        if name not in existing:
            op.add_column("questions", column)

    # All rows predating this workflow remain usable without invented citations.
    # New rows receive the column defaults (draft and citation required).
    op.execute(
        sa.text(
            """
            UPDATE questions
            SET workflow_status = CASE WHEN is_published THEN 'published' ELSE 'draft' END,
                requires_citation = false,
                published_at = CASE
                    WHEN is_published THEN COALESCE(published_at, updated_at, created_at)
                    ELSE published_at
                END
            """
        )
    )


def upgrade() -> None:
    _add_question_workflow_columns()
    existing_tables = _table_names()

    if "source_documents" not in existing_tables:
        op.create_table(
            "source_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("public_id", sa.String(length=36), nullable=False),
            sa.Column(
                "subject_id",
                sa.Integer(),
                sa.ForeignKey("subjects.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "course_id",
                sa.Integer(),
                sa.ForeignKey("courses.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("kind", sa.String(length=50), nullable=False, server_default="material"),
            sa.Column(
                "rights_status",
                sa.String(length=40),
                nullable=False,
                server_default="internal_learning",
            ),
            sa.Column("attribution", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="inbox"),
            sa.Column(
                "created_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "reviewed_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("archived_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    _create_index_if_missing(
        "ix_source_documents_public_id", "source_documents", ["public_id"], unique=True
    )
    _create_index_if_missing(
        "ix_source_documents_status_subject", "source_documents", ["status", "subject_id"]
    )
    _create_index_if_missing(
        "ix_source_documents_status_course", "source_documents", ["status", "course_id"]
    )

    if "source_blobs" not in existing_tables:
        op.create_table(
            "source_blobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False),
            sa.Column("media_type", sa.String(length=255), nullable=False),
            sa.Column("extension", sa.String(length=20), nullable=False),
            sa.Column("storage_backend", sa.String(length=20), nullable=False),
            sa.Column("storage_key", sa.String(length=1024), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    _create_index_if_missing("ix_source_blobs_sha256", "source_blobs", ["sha256"], unique=True)

    if "source_versions" not in existing_tables:
        op.create_table(
            "source_versions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "document_id",
                sa.Integer(),
                sa.ForeignKey("source_documents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "blob_id",
                sa.Integer(),
                sa.ForeignKey("source_blobs.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("original_filename", sa.String(length=512), nullable=False),
            sa.Column("page_count", sa.Integer(), nullable=True),
            sa.Column(
                "uploaded_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "document_id", "version_number", name="uq_source_version_number"
            ),
            sa.UniqueConstraint("document_id", "blob_id", name="uq_source_version_blob"),
        )
    _create_index_if_missing(
        "ix_source_versions_document_created", "source_versions", ["document_id", "created_at"]
    )

    if "source_document_topics" not in existing_tables:
        op.create_table(
            "source_document_topics",
            sa.Column(
                "document_id",
                sa.Integer(),
                sa.ForeignKey("source_documents.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "topic_id",
                sa.Integer(),
                sa.ForeignKey("topics.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if "source_bookmarks" not in existing_tables:
        op.create_table(
            "source_bookmarks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_version_id", sa.Integer(), sa.ForeignKey("source_versions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id", "document_id", name="uq_source_bookmark_user_document"),
        )
    _create_index_if_missing(
        "ix_source_bookmarks_user_created", "source_bookmarks", ["user_id", "created_at"]
    )

    if "source_read_progress" not in existing_tables:
        op.create_table(
            "source_read_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_version_id", sa.Integer(), sa.ForeignKey("source_versions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("last_page", sa.Integer(), nullable=True),
            sa.Column("progress_percent", sa.Float(), nullable=False, server_default="0"),
            sa.Column("last_opened_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id", "document_id", name="uq_source_progress_user_document"),
        )
    _create_index_if_missing(
        "ix_source_read_progress_user_opened",
        "source_read_progress",
        ["user_id", "last_opened_at"],
    )

    if "source_read_events" not in existing_tables:
        op.create_table(
            "source_read_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_version_id", sa.Integer(), sa.ForeignKey("source_versions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("event_type", sa.String(length=30), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("session_id", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    _create_index_if_missing(
        "ix_source_read_events_user_created", "source_read_events", ["user_id", "created_at"]
    )
    _create_index_if_missing(
        "ix_source_read_events_document_created",
        "source_read_events",
        ["document_id", "created_at"],
    )

    if "source_workflow_events" not in existing_tables:
        op.create_table(
            "source_workflow_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("from_status", sa.String(length=30), nullable=True),
            sa.Column("to_status", sa.String(length=30), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    _create_index_if_missing(
        "ix_source_workflow_document_created",
        "source_workflow_events",
        ["document_id", "created_at"],
    )

    if "question_source_citations" not in existing_tables:
        op.create_table(
            "question_source_citations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_version_id", sa.Integer(), sa.ForeignKey("source_versions.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("page_start", sa.Integer(), nullable=True),
            sa.Column("page_end", sa.Integer(), nullable=True),
            sa.Column("section_label", sa.String(length=255), nullable=True),
            sa.Column("locator_text", sa.String(length=500), nullable=True),
            sa.Column("excerpt", sa.Text(), nullable=True),
            sa.Column("purpose", sa.String(length=30), nullable=False),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("verified_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("verified_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    _create_index_if_missing(
        "ix_question_source_citations_question", "question_source_citations", ["question_id"]
    )
    _create_index_if_missing(
        "ix_question_source_citations_version", "question_source_citations", ["source_version_id"]
    )

    if "source_reports" not in existing_tables:
        op.create_table(
            "source_reports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_version_id", sa.Integer(), sa.ForeignKey("source_versions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
            sa.Column("resolved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    _create_index_if_missing(
        "ix_source_reports_document_status", "source_reports", ["document_id", "status"]
    )
    _create_index_if_missing(
        "ix_source_reports_user_created", "source_reports", ["user_id", "created_at"]
    )


def downgrade() -> None:
    for table_name in (
        "source_reports",
        "question_source_citations",
        "source_workflow_events",
        "source_read_events",
        "source_read_progress",
        "source_bookmarks",
        "source_document_topics",
        "source_versions",
        "source_blobs",
        "source_documents",
    ):
        if table_name in _table_names():
            op.drop_table(table_name)

    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("questions")}
    for column_name in (
        "generation_metadata",
        "published_at",
        "review_notes",
        "reviewed_at",
        "reviewed_by_id",
        "generated_by_ai",
        "requires_citation",
        "workflow_status",
    ):
        if column_name in existing:
            op.drop_column("questions", column_name)
