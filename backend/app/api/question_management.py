"""Instructor/admin question drafting, review, citations, and publication."""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.database import get_db
from app.core.permissions import UserRole, require_role
from app.models.models import (
    Question,
    QuestionAnswer,
    QuestionBank,
    QuestionDifficulty,
    QuestionSourceCitation,
    QuestionType,
    QuestionWorkflowStatus,
    SourceStatus,
    SourceVersion,
    Topic,
)
from app.services.question_generation import (
    QuestionGenerationError,
    extract_source_text,
    generate_questions_from_text,
    get_openai_config,
)
from app.services.question_workflow import (
    QuestionWorkflowError,
    archive_question,
    citation_payload,
    lock_question,
    publish_question,
    reset_question_to_draft,
    review_question,
    submit_question_for_review,
    unpublish_question,
    validate_citation_locator,
    validate_source_matches_question,
)


router = APIRouter()
staff_dependency = require_role([UserRole.INSTRUCTOR, UserRole.ADMIN])
DANGEROUS_HTML = re.compile(
    r"<\s*(?:script|iframe|object|embed|form)\b|\bon[a-z]+\s*=|javascript\s*:",
    re.IGNORECASE,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnswerInput(StrictModel):
    text: str = Field(min_length=1, max_length=500)
    is_correct: bool = False
    order: int = Field(default=0, ge=0, le=100)
    explanation: str | None = Field(default=None, max_length=2000)


class QuestionDraftInput(StrictModel):
    topic_id: int | None = Field(default=None, ge=1)
    question_bank_id: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=3, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    question_type: QuestionType
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM
    content_html: str = Field(min_length=3, max_length=50_000)
    solution_html: str | None = Field(default=None, max_length=50_000)
    explanation: str | None = Field(default=None, max_length=10_000)
    bloom_level: str | None = Field(default=None, max_length=50)
    estimated_time_minutes: int = Field(default=5, ge=1, le=180)
    xp_reward: int | None = Field(default=None, ge=0, le=500)
    expected_answer: str | None = Field(default=None, max_length=255)
    numerical_tolerance: float | None = Field(default=None, ge=0)
    accepted_units: list[str] = Field(default_factory=list, max_length=30)
    coding_language: str | None = Field(default=None, max_length=50)
    starter_code: str | None = Field(default=None, max_length=50_000)
    test_cases: list[dict] | None = None
    answers: list[AnswerInput] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def has_location(self):
        if self.topic_id is None and self.question_bank_id is None:
            raise ValueError("topic_id or question_bank_id is required")
        return self


class QuestionPatchInput(StrictModel):
    topic_id: int | None = Field(default=None, ge=1)
    question_bank_id: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=3, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    question_type: QuestionType | None = None
    difficulty: QuestionDifficulty | None = None
    content_html: str | None = Field(default=None, min_length=3, max_length=50_000)
    solution_html: str | None = Field(default=None, max_length=50_000)
    explanation: str | None = Field(default=None, max_length=10_000)
    bloom_level: str | None = Field(default=None, max_length=50)
    estimated_time_minutes: int | None = Field(default=None, ge=1, le=180)
    xp_reward: int | None = Field(default=None, ge=0, le=500)
    expected_answer: str | None = Field(default=None, max_length=255)
    numerical_tolerance: float | None = Field(default=None, ge=0)
    accepted_units: list[str] | None = Field(default=None, max_length=30)
    coding_language: str | None = Field(default=None, max_length=50)
    starter_code: str | None = Field(default=None, max_length=50_000)
    test_cases: list[dict] | None = None
    answers: list[AnswerInput] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def required_fields_cannot_be_cleared(self):
        for field in ("title", "question_type", "difficulty", "content_html"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CitationInput(StrictModel):
    source_version_id: int = Field(ge=1)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_label: str | None = Field(default=None, max_length=255)
    locator_text: str | None = Field(default=None, max_length=500)
    excerpt: str | None = Field(default=None, max_length=4000)
    purpose: Literal["prompt", "solution", "explanation"] = "prompt"


class ReviewInput(StrictModel):
    action: Literal["approve", "reject"]
    notes: str | None = Field(default=None, max_length=4000)


class GenerateInput(StrictModel):
    topic_id: int | None = Field(default=None, ge=1)
    question_bank_id: int | None = Field(default=None, ge=1)
    source_version_id: int = Field(ge=1)
    count: int = Field(default=3, ge=1, le=10)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_label: str | None = Field(default=None, max_length=255)
    locator_text: str | None = Field(default=None, max_length=500)
    guidance: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def has_location(self):
        if self.topic_id is None and self.question_bank_id is None:
            raise ValueError("topic_id or question_bank_id is required")
        if self.page_end is not None and self.page_start is None:
            raise ValueError("page_end requires page_start")
        return self


def _raise_workflow(error: QuestionWorkflowError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


def _resolve_bank(
    db: Session,
    *,
    topic_id: int | None,
    question_bank_id: int | None,
) -> QuestionBank:
    if question_bank_id is not None:
        bank = db.query(QuestionBank).filter(QuestionBank.id == question_bank_id).first()
        if bank is None:
            raise HTTPException(status_code=404, detail="Question bank not found")
        if topic_id is not None and bank.topic_id != topic_id:
            raise HTTPException(status_code=422, detail="Question bank does not belong to topic")
        return bank
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    bank = (
        db.query(QuestionBank)
        .filter(
            QuestionBank.topic_id == topic.id,
            QuestionBank.name == "Instructor Review Bank",
        )
        .first()
    )
    if bank is None:
        bank = QuestionBank(
            topic_id=topic.id,
            name="Instructor Review Bank",
            description="Human-reviewed source-grounded questions.",
        )
        db.add(bank)
        db.flush()
    return bank


def _validate_safe_html(value: str | None) -> None:
    if value and DANGEROUS_HTML.search(value):
        raise HTTPException(status_code=422, detail="Question HTML contains unsafe markup")


def _replace_answers(question: Question, answers: list[AnswerInput]) -> None:
    question.answers.clear()
    for item in answers:
        question.answers.append(
            QuestionAnswer(
                text=item.text.strip(),
                is_correct=item.is_correct,
                order=item.order,
                explanation=item.explanation,
            )
        )
    correct = next((answer for answer in question.answers if answer.is_correct), None)
    if correct is not None and (
        question.question_type == QuestionType.MULTIPLE_CHOICE
        or not (question.expected_answer or "").strip()
    ):
        question.expected_answer = correct.text


EDITABLE_FIELDS = {
    "title",
    "description",
    "question_type",
    "difficulty",
    "content_html",
    "solution_html",
    "explanation",
    "bloom_level",
    "estimated_time_minutes",
    "xp_reward",
    "expected_answer",
    "numerical_tolerance",
    "accepted_units",
    "coding_language",
    "starter_code",
    "test_cases",
}


def _apply_fields(question: Question, values: dict) -> None:
    _validate_safe_html(values.get("content_html"))
    _validate_safe_html(values.get("solution_html"))
    for field in EDITABLE_FIELDS.intersection(values):
        value = values[field]
        if field in {"question_type", "difficulty"} and value is not None:
            setattr(question, field, value)
        elif field == "accepted_units" and value is not None:
            question.accepted_units = [unit.strip() for unit in value if unit.strip()]
        else:
            setattr(question, field, value)


def _question_payload(question: Question) -> dict:
    topic = question.question_bank.topic
    return {
        "id": question.id,
        "title": question.title,
        "description": question.description,
        "question_type": question.question_type.value,
        "difficulty": question.difficulty.value,
        "content_html": question.content_html,
        "solution_html": question.solution_html,
        "explanation": question.explanation,
        "expected_answer": question.expected_answer,
        "numerical_tolerance": question.numerical_tolerance,
        "accepted_units": question.accepted_units or [],
        "bloom_level": question.bloom_level,
        "estimated_time_minutes": question.estimated_time_minutes,
        "xp_reward": question.xp_reward,
        "coding_language": question.coding_language,
        "starter_code": question.starter_code,
        "test_cases": question.test_cases,
        "workflow_status": question.workflow_status,
        "is_published": question.is_published,
        "requires_citation": question.requires_citation,
        "generated_by_ai": question.generated_by_ai,
        "reviewed_by_id": question.reviewed_by_id,
        "reviewed_at": question.reviewed_at,
        "review_notes": question.review_notes,
        "published_at": question.published_at,
        "author_id": question.author_id,
        "topic": {"id": topic.id, "name": topic.name},
        "subject": {"id": topic.subject.id, "name": topic.subject.name},
        "question_bank_id": question.question_bank_id,
        "answers": [
            {
                "id": answer.id,
                "text": answer.text,
                "is_correct": answer.is_correct,
                "order": answer.order,
                "explanation": answer.explanation,
            }
            for answer in sorted(question.answers, key=lambda item: item.order)
        ],
        "citations": [citation_payload(item, include_excerpt=True) for item in question.citations],
        "created_at": question.created_at,
        "updated_at": question.updated_at,
    }


def _question_query(db: Session):
    return db.query(Question).options(
        joinedload(Question.question_bank)
        .joinedload(QuestionBank.topic)
        .joinedload(Topic.subject),
        selectinload(Question.answers),
        selectinload(Question.citations)
        .selectinload(QuestionSourceCitation.source_version)
        .selectinload(SourceVersion.document),
    )


@router.get("")
@router.get("/", include_in_schema=False)
def list_managed_questions(
    workflow_status: QuestionWorkflowStatus | None = None,
    topic_id: int | None = Query(default=None, ge=1),
    source_document_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user=Depends(staff_dependency),
    db: Session = Depends(get_db),
):
    del current_user
    query = _question_query(db)
    if workflow_status is not None:
        query = query.filter(Question.workflow_status == workflow_status.value)
    if topic_id is not None:
        query = query.join(QuestionBank).filter(QuestionBank.topic_id == topic_id)
    if source_document_id is not None:
        query = (
            query.join(QuestionSourceCitation)
            .join(SourceVersion)
            .filter(SourceVersion.document_id == source_document_id)
            .distinct()
        )
    total = query.count()
    questions = query.order_by(Question.updated_at.desc(), Question.id.desc()).offset(offset).limit(limit).all()
    return {"total": total, "offset": offset, "limit": limit, "questions": [_question_payload(item) for item in questions]}


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_question_draft(
    payload: QuestionDraftInput,
    current_user=Depends(staff_dependency),
    db: Session = Depends(get_db),
):
    bank = _resolve_bank(
        db,
        topic_id=payload.topic_id,
        question_bank_id=payload.question_bank_id,
    )
    values = payload.model_dump(exclude={"topic_id", "question_bank_id", "answers"})
    question = Question(
        question_bank_id=bank.id,
        title=payload.title.strip(),
        question_type=payload.question_type,
        difficulty=payload.difficulty,
        content_html=payload.content_html,
        author_id=current_user.id,
        workflow_status=QuestionWorkflowStatus.DRAFT.value,
        is_published=False,
        requires_citation=True,
        generated_by_ai=False,
    )
    _apply_fields(question, values)
    db.add(question)
    _replace_answers(question, payload.answers)
    db.commit()
    return _question_payload(question)


@router.patch("/{question_id}")
def update_question_draft(
    question_id: int,
    payload: QuestionPatchInput,
    current_user=Depends(staff_dependency),
    db: Session = Depends(get_db),
):
    del current_user
    try:
        question = lock_question(db, question_id)
        if question.workflow_status == QuestionWorkflowStatus.ARCHIVED.value:
            raise QuestionWorkflowError("Archived questions cannot be edited", 409)
        values = payload.model_dump(exclude_unset=True)
        if "topic_id" in values or "question_bank_id" in values:
            bank = _resolve_bank(
                db,
                topic_id=values.pop("topic_id", None),
                question_bank_id=values.pop("question_bank_id", None),
            )
            question.question_bank_id = bank.id
            question.question_bank = bank
        answers = values.pop("answers", None)
        _apply_fields(question, values)
        if answers is not None:
            _replace_answers(question, [AnswerInput.model_validate(item) for item in answers])
        reset_question_to_draft(question)
        db.commit()
        return _question_payload(question)
    except QuestionWorkflowError as error:
        db.rollback()
        _raise_workflow(error)


@router.post("/{question_id}/citations", status_code=status.HTTP_201_CREATED)
def add_question_citation(
    question_id: int,
    payload: CitationInput,
    current_user=Depends(staff_dependency),
    db: Session = Depends(get_db),
):
    try:
        question = lock_question(db, question_id)
        if question.workflow_status == QuestionWorkflowStatus.ARCHIVED.value:
            raise QuestionWorkflowError("Archived questions cannot be edited", 409)
        version = (
            db.query(SourceVersion)
            .options(
                joinedload(SourceVersion.document),
                joinedload(SourceVersion.blob),
            )
            .filter(SourceVersion.id == payload.source_version_id)
            .first()
        )
        if version is None:
            raise QuestionWorkflowError("Source version not found", 404)
        validate_citation_locator(
            version,
            page_start=payload.page_start,
            page_end=payload.page_end,
            section_label=payload.section_label,
            locator_text=payload.locator_text,
            purpose=payload.purpose,
        )
        validate_source_matches_question(question, version)
        citation = QuestionSourceCitation(
            question_id=question.id,
            source_version_id=version.id,
            page_start=payload.page_start,
            page_end=payload.page_end,
            section_label=payload.section_label.strip() if payload.section_label else None,
            locator_text=payload.locator_text.strip() if payload.locator_text else None,
            excerpt=payload.excerpt.strip() if payload.excerpt else None,
            purpose=payload.purpose,
            created_by_id=current_user.id,
        )
        question.citations.append(citation)
        reset_question_to_draft(question)
        db.commit()
        return citation_payload(citation, include_excerpt=True)
    except QuestionWorkflowError as error:
        db.rollback()
        _raise_workflow(error)


@router.delete("/{question_id}/citations/{citation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question_citation(
    question_id: int,
    citation_id: int,
    current_user=Depends(staff_dependency),
    db: Session = Depends(get_db),
):
    del current_user
    try:
        question = lock_question(db, question_id)
        if question.workflow_status == QuestionWorkflowStatus.ARCHIVED.value:
            raise QuestionWorkflowError("Archived questions cannot be edited", 409)
        citation = (
            db.query(QuestionSourceCitation)
            .filter(
                QuestionSourceCitation.id == citation_id,
                QuestionSourceCitation.question_id == question.id,
            )
            .first()
        )
        if citation is None:
            raise QuestionWorkflowError("Citation not found", 404)
        db.delete(citation)
        reset_question_to_draft(question)
        db.commit()
        return None
    except QuestionWorkflowError as error:
        db.rollback()
        _raise_workflow(error)


@router.post("/{question_id}/submit-review")
def submit_for_review(
    question_id: int,
    current_user=Depends(staff_dependency),
    db: Session = Depends(get_db),
):
    del current_user
    try:
        question = lock_question(db, question_id)
        submit_question_for_review(question)
        db.commit()
        return _question_payload(question)
    except QuestionWorkflowError as error:
        db.rollback()
        _raise_workflow(error)


@router.post("/{question_id}/review")
def review_pending_question(
    question_id: int,
    payload: ReviewInput,
    current_user=Depends(staff_dependency),
    db: Session = Depends(get_db),
):
    try:
        question = lock_question(db, question_id)
        review_question(
            question,
            reviewer_id=current_user.id,
            approve=payload.action == "approve",
            notes=payload.notes,
        )
        db.commit()
        return _question_payload(question)
    except QuestionWorkflowError as error:
        db.rollback()
        _raise_workflow(error)


@router.post("/{question_id}/publish")
def publish_approved_question(
    question_id: int,
    current_user=Depends(staff_dependency),
    db: Session = Depends(get_db),
):
    del current_user
    try:
        question = lock_question(db, question_id)
        publish_question(question)
        db.commit()
        return _question_payload(question)
    except QuestionWorkflowError as error:
        db.rollback()
        _raise_workflow(error)


@router.post("/{question_id}/unpublish")
def unpublish_live_question(
    question_id: int,
    current_user=Depends(staff_dependency),
    db: Session = Depends(get_db),
):
    del current_user
    try:
        question = lock_question(db, question_id)
        unpublish_question(question)
        db.commit()
        return _question_payload(question)
    except QuestionWorkflowError as error:
        db.rollback()
        _raise_workflow(error)


@router.post("/{question_id}/archive")
def archive_managed_question(
    question_id: int,
    current_user=Depends(staff_dependency),
    db: Session = Depends(get_db),
):
    del current_user
    try:
        question = lock_question(db, question_id)
        archive_question(question)
        db.commit()
        return _question_payload(question)
    except QuestionWorkflowError as error:
        db.rollback()
        _raise_workflow(error)


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_question_drafts(
    payload: GenerateInput,
    current_user=Depends(staff_dependency),
    db: Session = Depends(get_db),
):
    bank = _resolve_bank(
        db,
        topic_id=payload.topic_id,
        question_bank_id=payload.question_bank_id,
    )
    version = (
        db.query(SourceVersion)
        .options(
            joinedload(SourceVersion.document),
            joinedload(SourceVersion.blob),
        )
        .filter(SourceVersion.id == payload.source_version_id)
        .first()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Source version not found")
    if version.document.status != SourceStatus.PUBLISHED.value:
        raise HTTPException(status_code=422, detail="AI drafts require a published source")
    try:
        get_openai_config()
        validate_citation_locator(
            version,
            page_start=payload.page_start,
            page_end=payload.page_end,
            section_label=payload.section_label,
            locator_text=payload.locator_text,
            purpose="prompt",
        )
        source_text = await run_in_threadpool(
            extract_source_text,
            version,
            page_start=payload.page_start,
            page_end=payload.page_end,
        )
        generated, provider_metadata = await generate_questions_from_text(
            source_text=source_text,
            subject_name=bank.topic.subject.name,
            topic_name=bank.topic.name,
            count=payload.count,
            guidance=payload.guidance,
        )
    except QuestionWorkflowError as error:
        db.rollback()
        _raise_workflow(error)
    except QuestionGenerationError as error:
        db.rollback()
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

    questions = []
    try:
        for draft in generated:
            question = Question(
                question_bank_id=bank.id,
                title=draft.title,
                question_type=QuestionType(draft.question_type),
                difficulty=QuestionDifficulty(draft.difficulty),
                content_html=draft.content_html,
                solution_html=draft.solution_html,
                explanation=draft.explanation,
                expected_answer=draft.expected_answer,
                numerical_tolerance=draft.numerical_tolerance,
                accepted_units=draft.accepted_units,
                bloom_level=draft.bloom_level,
                estimated_time_minutes=draft.estimated_time_minutes,
                xp_reward=draft.xp_reward,
                author_id=current_user.id,
                workflow_status=QuestionWorkflowStatus.DRAFT.value,
                is_published=False,
                requires_citation=True,
                generated_by_ai=True,
                generation_metadata={
                    **provider_metadata,
                    "source_version_id": version.id,
                    "page_start": payload.page_start,
                    "page_end": payload.page_end,
                },
            )
            citation = QuestionSourceCitation(
                source_version_id=version.id,
                page_start=payload.page_start,
                page_end=payload.page_end,
                section_label=payload.section_label.strip() if payload.section_label else None,
                locator_text=payload.locator_text.strip() if payload.locator_text else None,
                purpose="prompt",
                created_by_id=current_user.id,
            )
            question.citations.append(citation)
            db.add(question)
            db.flush()
            validate_source_matches_question(question, version)
            questions.append(question)
        db.commit()
    except QuestionWorkflowError as error:
        db.rollback()
        _raise_workflow(error)
    return {
        "count": len(questions),
        "workflow_status": QuestionWorkflowStatus.DRAFT.value,
        "questions": [_question_payload(question) for question in questions],
    }
