"""Editorial workflow and learner-safe source citations for questions."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.models.models import (
    Question,
    QuestionSourceCitation,
    QuestionType,
    QuestionWorkflowStatus,
    SourceStatus,
    SourceVersion,
)


ALLOWED_CITATION_PURPOSES = {"prompt", "solution", "explanation"}


class QuestionWorkflowError(ValueError):
    """A state transition or editorial validation failed."""

    def __init__(self, detail: str, status_code: int = 422):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def learner_question_filters() -> tuple:
    """Return the complete visibility contract for learner-facing queries."""
    return (
        Question.is_published.is_(True),
        Question.workflow_status == QuestionWorkflowStatus.PUBLISHED.value,
    )


def is_learner_visible(question: Question) -> bool:
    return bool(
        question.is_published
        and question.workflow_status == QuestionWorkflowStatus.PUBLISHED.value
    )


def _clean_locator(value: str | None) -> str | None:
    cleaned = value.strip() if value else None
    return cleaned or None


def validate_citation_locator(
    version: SourceVersion,
    *,
    page_start: int | None,
    page_end: int | None,
    section_label: str | None,
    locator_text: str | None,
    purpose: str,
) -> None:
    """Validate an exact, useful locator before it is persisted."""
    if purpose not in ALLOWED_CITATION_PURPOSES:
        raise QuestionWorkflowError("Unknown citation purpose")
    if page_start is not None and page_start < 1:
        raise QuestionWorkflowError("Citation page_start must be at least 1")
    if page_end is not None:
        if page_start is None:
            raise QuestionWorkflowError("Citation page_end requires page_start")
        if page_end < page_start:
            raise QuestionWorkflowError("Citation page_end cannot precede page_start")
    if version.page_count and page_start and page_start > version.page_count:
        raise QuestionWorkflowError("Citation starts beyond the end of this source version")
    if version.page_count and page_end and page_end > version.page_count:
        raise QuestionWorkflowError("Citation ends beyond the end of this source version")
    if page_start is None and not (_clean_locator(section_label) or _clean_locator(locator_text)):
        raise QuestionWorkflowError("A citation needs a page, section, or locator")


def validate_source_matches_question(question: Question, version: SourceVersion) -> None:
    """Prevent citations from silently crossing classified subjects or topics."""
    topic = question.question_bank.topic
    document = version.document
    document_subject_id = document.subject_id
    if document_subject_id is None and document.course is not None:
        document_subject_id = document.course.subject_id
    if document_subject_id is not None and document_subject_id != topic.subject_id:
        raise QuestionWorkflowError("The source and question belong to different subjects")

    linked_topic_ids = {link.topic_id for link in document.topic_links}
    if linked_topic_ids and topic.id not in linked_topic_ids:
        raise QuestionWorkflowError("The source is not classified for this question topic")


def validate_question_content(question: Question) -> None:
    """Check fields required by the deterministic learner assessment flow."""
    if not (question.title or "").strip():
        raise QuestionWorkflowError("Question title is required")
    if not (question.content_html or "").strip():
        raise QuestionWorkflowError("Question content is required")
    if question.question_bank is None or question.question_bank.topic is None:
        raise QuestionWorkflowError("Question must belong to a topic question bank")
    if not question.coding_language and not (question.expected_answer or "").strip():
        raise QuestionWorkflowError("A deterministic expected answer is required")
    if question.question_type == QuestionType.MULTIPLE_CHOICE:
        if len(question.answers) < 2 or sum(answer.is_correct for answer in question.answers) != 1:
            raise QuestionWorkflowError(
                "Multiple-choice questions need at least two options and exactly one correct option"
            )


def validate_question_citations(question: Question, *, require_published_source: bool) -> None:
    if question.requires_citation and not question.citations:
        raise QuestionWorkflowError("At least one source citation is required")

    for citation in question.citations:
        version = citation.source_version
        validate_citation_locator(
            version,
            page_start=citation.page_start,
            page_end=citation.page_end,
            section_label=citation.section_label,
            locator_text=citation.locator_text,
            purpose=citation.purpose,
        )
        validate_source_matches_question(question, version)
        if (
            require_published_source
            and version.document.status != SourceStatus.PUBLISHED.value
        ):
            raise QuestionWorkflowError(
                "Every cited source must be published before the question can be published"
            )


def validate_question_for_review(question: Question) -> None:
    validate_question_content(question)
    validate_question_citations(question, require_published_source=False)


def validate_question_for_publish(question: Question) -> None:
    validate_question_content(question)
    validate_question_citations(question, require_published_source=True)


def reset_question_to_draft(question: Question) -> None:
    """Invalidate earlier approval whenever editable content/provenance changes."""
    question.workflow_status = QuestionWorkflowStatus.DRAFT.value
    question.is_published = False
    question.reviewed_by_id = None
    question.reviewed_at = None
    question.review_notes = None
    question.published_at = None
    for citation in question.citations:
        citation.verified_by_id = None
        citation.verified_at = None


def submit_question_for_review(question: Question) -> None:
    if question.workflow_status not in {
        QuestionWorkflowStatus.DRAFT.value,
        QuestionWorkflowStatus.REJECTED.value,
    }:
        raise QuestionWorkflowError("Only draft or rejected questions can be submitted", 409)
    validate_question_for_review(question)
    question.workflow_status = QuestionWorkflowStatus.PENDING_REVIEW.value
    question.is_published = False


def review_question(
    question: Question,
    *,
    reviewer_id: int,
    approve: bool,
    notes: str | None,
) -> None:
    if question.workflow_status != QuestionWorkflowStatus.PENDING_REVIEW.value:
        raise QuestionWorkflowError("Only pending questions can be reviewed", 409)
    cleaned_notes = _clean_locator(notes)
    if not approve and not cleaned_notes:
        raise QuestionWorkflowError("Rejection notes are required")

    now = datetime.utcnow()
    question.workflow_status = (
        QuestionWorkflowStatus.APPROVED.value
        if approve
        else QuestionWorkflowStatus.REJECTED.value
    )
    question.is_published = False
    question.reviewed_by_id = reviewer_id
    question.reviewed_at = now
    question.review_notes = cleaned_notes
    if approve:
        validate_question_for_review(question)
        for citation in question.citations:
            citation.verified_by_id = reviewer_id
            citation.verified_at = now


def publish_question(question: Question) -> None:
    if question.workflow_status != QuestionWorkflowStatus.APPROVED.value:
        raise QuestionWorkflowError("Only approved questions can be published", 409)
    validate_question_for_publish(question)
    question.workflow_status = QuestionWorkflowStatus.PUBLISHED.value
    question.is_published = True
    question.published_at = datetime.utcnow()


def unpublish_question(question: Question) -> None:
    if question.workflow_status != QuestionWorkflowStatus.PUBLISHED.value:
        raise QuestionWorkflowError("Only published questions can be unpublished", 409)
    question.workflow_status = QuestionWorkflowStatus.APPROVED.value
    question.is_published = False
    question.published_at = None


def archive_question(question: Question) -> None:
    if question.workflow_status == QuestionWorkflowStatus.ARCHIVED.value:
        raise QuestionWorkflowError("Question is already archived", 409)
    question.workflow_status = QuestionWorkflowStatus.ARCHIVED.value
    question.is_published = False
    question.published_at = None


def citation_payload(citation: QuestionSourceCitation, *, include_excerpt: bool = False) -> dict:
    version = citation.source_version
    document = version.document
    # The immutable database version id is the content selector. The human
    # version number remains in the URL as display metadata only.
    page_suffix = f"?version_id={version.id}&version={version.version_number}"
    if citation.page_start:
        page_suffix += f"&page={citation.page_start}"
    payload = {
        "id": citation.id,
        "public_id": str(document.public_id),
        "title": document.title,
        "version": version.version_number,
        "page_start": citation.page_start,
        "page_end": citation.page_end,
        "section_label": citation.section_label,
        "locator_text": citation.locator_text,
        "purpose": citation.purpose,
        "href": f"/sources/{quote(str(document.public_id), safe='')}{page_suffix}",
    }
    if include_excerpt:
        payload["excerpt"] = citation.excerpt
    return payload


def learner_source_recommendations(
    question: Question,
    *,
    purposes: Iterable[str] | None = None,
) -> list[dict]:
    """Return published, verified citations without excerpts or solution content."""
    allowed = set(purposes) if purposes is not None else None
    result: list[dict] = []
    seen: set[tuple] = set()
    for citation in question.citations:
        if allowed is not None and citation.purpose not in allowed:
            continue
        if citation.source_version.document.status != SourceStatus.PUBLISHED.value:
            continue
        # New workflow citations are reviewer-verified. Grandfathered questions
        # can be learner-visible without citations, never with unverified ones.
        if citation.verified_at is None:
            continue
        key = (
            citation.source_version_id,
            citation.page_start,
            citation.page_end,
            citation.section_label,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(citation_payload(citation))
    return result


def lock_question(db: Session, question_id: int) -> Question:
    question = (
        db.query(Question)
        .filter(Question.id == question_id)
        .with_for_update()
        .first()
    )
    if question is None:
        raise QuestionWorkflowError("Question not found", 404)
    return question
