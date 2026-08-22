"""Instructor/admin workflow for private learning sources."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import UserRole, require_role
from app.models.models import (
    Course,
    Question,
    QuestionSourceCitation,
    QuestionWorkflowStatus,
    SourceBlob,
    SourceDocument,
    SourceDocumentTopic,
    SourceReport,
    SourceStatus,
    SourceVersion,
    SourceWorkflowEvent,
    Subject,
    Topic,
)
from app.services.source_ingestion import ingest_source_file

router = APIRouter()
staff_user = require_role([UserRole.INSTRUCTOR, UserRole.ADMIN])


class SourceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    kind: str | None = Field(default=None, min_length=2, max_length=40)
    subject_id: int | None = None
    course_id: int | None = None
    topic_ids: list[int] | None = None
    rights_status: str | None = Field(default=None, min_length=2, max_length=40)
    attribution: str | None = Field(default=None, max_length=1000)


class WorkflowPayload(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class ReportResolution(BaseModel):
    status: str = Field(pattern="^(resolved|dismissed)$")


def _status(status: SourceStatus | str) -> str:
    return status.value if isinstance(status, SourceStatus) else str(status)


def _parse_topic_ids(value: str | None) -> list[int]:
    if not value:
        return []
    try:
        return sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    except ValueError as error:
        raise HTTPException(status_code=422, detail="topic_ids must be comma-separated integers") from error


def _scope_query(db: Session, current_user):
    query = db.query(SourceDocument)
    if current_user.role != UserRole.ADMIN:
        query = query.outerjoin(Course, Course.id == SourceDocument.course_id).filter(
            or_(SourceDocument.created_by_id == current_user.id, Course.instructor_id == current_user.id)
        )
    return query


def _owned_document(db: Session, source_id: str, current_user, *, lock: bool = False) -> SourceDocument:
    query = _scope_query(db, current_user).filter(SourceDocument.public_id == source_id)
    if lock:
        query = query.with_for_update()
    document = query.first()
    if document is None:
        raise HTTPException(status_code=404, detail="Source document not found")
    return document


def _latest_version(db: Session, document_id: int) -> SourceVersion | None:
    return db.query(SourceVersion).filter_by(document_id=document_id).order_by(SourceVersion.version_number.desc()).first()


def _staff_document(db: Session, document: SourceDocument) -> dict:
    subject = db.query(Subject).filter_by(id=document.subject_id).first() if document.subject_id else None
    course = db.query(Course).filter_by(id=document.course_id).first() if document.course_id else None
    topics = (
        db.query(Topic, SourceDocumentTopic.is_primary)
        .join(SourceDocumentTopic, SourceDocumentTopic.topic_id == Topic.id)
        .filter(SourceDocumentTopic.document_id == document.id)
        .order_by(SourceDocumentTopic.is_primary.desc(), Topic.name)
        .all()
    )
    versions = db.query(SourceVersion).filter_by(document_id=document.id).order_by(SourceVersion.version_number.desc()).all()
    version_rows = []
    for version in versions:
        blob = db.query(SourceBlob).filter_by(id=version.blob_id).first()
        if blob:
            version_rows.append({
                "id": version.id,
                "version_number": version.version_number,
                "file_name": version.original_filename,
                "extension": blob.extension.lstrip("."),
                "content_type": blob.media_type,
                "size_bytes": blob.size_bytes,
                "sha256": blob.sha256,
                "page_count": version.page_count,
                "notes": version.notes,
                "created_at": version.created_at,
            })
    active_version = version_rows[0] if version_rows else None
    return {
        "id": document.public_id,
        "title": document.title,
        "name": active_version["file_name"] if active_version else document.title,
        "description": document.description,
        "kind": document.kind,
        "status": _status(document.status),
        "extension": active_version["extension"] if active_version else "",
        "size_bytes": active_version["size_bytes"] if active_version else 0,
        "content_type": active_version["content_type"] if active_version else "application/octet-stream",
        "rights_status": document.rights_status,
        "attribution": document.attribution,
        "subject": {"id": subject.id, "name": subject.name, "slug": subject.slug} if subject else None,
        "course": {"id": course.id, "name": course.name} if course else None,
        "topics": [{"id": topic.id, "name": topic.name, "slug": topic.slug, "is_primary": primary} for topic, primary in topics],
        "version": active_version,
        "versions": version_rows,
        "is_bookmarked": False,
        "reading_progress": 0,
        "last_page": None,
        "report_count": db.query(SourceReport).filter_by(document_id=document.id, status="open").count(),
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "reviewed_at": document.reviewed_at,
        "published_at": document.published_at,
        "archived_at": document.archived_at,
    }


async def _save_upload(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "source").suffix
    temp = tempfile.NamedTemporaryFile(prefix="electroquest-source-", suffix=suffix, delete=False)
    temp_path = Path(temp.name)
    total = 0
    try:
        with temp:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > settings.SOURCE_MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Source file is larger than the configured upload limit")
                temp.write(chunk)
        return temp_path
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def _check_taxonomy(db: Session, subject_id: int | None, course_id: int | None, topic_ids: list[int]) -> None:
    if subject_id is not None and db.query(Subject).filter_by(id=subject_id).first() is None:
        raise HTTPException(status_code=422, detail="Unknown subject")
    if course_id is not None:
        course = db.query(Course).filter_by(id=course_id).first()
        if course is None or (subject_id is not None and course.subject_id != subject_id):
            raise HTTPException(status_code=422, detail="Course does not belong to the selected subject")
    if topic_ids:
        topics = db.query(Topic).filter(Topic.id.in_(topic_ids)).all()
        if len(topics) != len(topic_ids) or (subject_id is not None and any(topic.subject_id != subject_id for topic in topics)):
            raise HTTPException(status_code=422, detail="A selected topic does not belong to the selected subject")


def _transition_source(db: Session, document: SourceDocument, actor_id: int, new_status: str, notes: str | None) -> None:
    """Record one source transition and keep cited questions learner-safe.

    The source row is already locked by the caller. Lock every question citing
    one of its immutable versions before a published source becomes unavailable;
    this closes the race with concurrent question publication and keeps both
    changes in the caller's transaction.
    """
    old_status = _status(document.status)
    if old_status == SourceStatus.PUBLISHED.value and new_status != SourceStatus.PUBLISHED.value:
        cited_question_ids = [
            question_id
            for (question_id,) in (
                db.query(QuestionSourceCitation.question_id)
                .join(SourceVersion, SourceVersion.id == QuestionSourceCitation.source_version_id)
                .filter(SourceVersion.document_id == document.id)
                .distinct()
                .all()
            )
        ]
        if cited_question_ids:
            cited_questions = (
                db.query(Question)
                .filter(Question.id.in_(cited_question_ids))
                .with_for_update()
                .all()
            )
            for question in cited_questions:
                was_published = (
                    question.workflow_status == QuestionWorkflowStatus.PUBLISHED.value
                    or question.is_published
                )
                if question.workflow_status == QuestionWorkflowStatus.PUBLISHED.value:
                    question.workflow_status = QuestionWorkflowStatus.APPROVED.value
                question.is_published = False
                if was_published:
                    question.published_at = None

    document.status = new_status
    document.updated_at = datetime.utcnow()
    db.add(SourceWorkflowEvent(document_id=document.id, actor_id=actor_id, from_status=old_status, to_status=new_status, notes=notes.strip() if notes else None))


@router.get("/taxonomy")
def taxonomy(current_user=Depends(staff_user), db: Session = Depends(get_db)):
    del current_user
    subjects = db.query(Subject).order_by(Subject.order, Subject.name).all()
    topics = db.query(Topic).order_by(Topic.subject_id, Topic.name).all()
    courses = db.query(Course).order_by(Course.subject_id, Course.name).all()
    return {
        "subjects": [{"id": row.id, "name": row.name, "slug": row.slug} for row in subjects],
        "topics": [{"id": row.id, "subject_id": row.subject_id, "name": row.name, "slug": row.slug} for row in topics],
        "courses": [{"id": row.id, "subject_id": row.subject_id, "name": row.name} for row in courses],
    }


@router.get("/dashboard")
def dashboard(current_user=Depends(staff_user), db: Session = Depends(get_db)):
    rows = _scope_query(db, current_user).with_entities(SourceDocument.status, func.count(SourceDocument.id)).group_by(SourceDocument.status).all()
    counts = {key: 0 for key in ("inbox", "review_pending", "published", "archived")}
    counts.update({_status(status): count for status, count in rows})
    question_query = db.query(Question)
    if current_user.role != UserRole.ADMIN:
        question_query = question_query.filter(Question.author_id == current_user.id)
    question_counts = dict(question_query.with_entities(Question.workflow_status, func.count(Question.id)).group_by(Question.workflow_status).all())
    return {"sources": counts, "questions": question_counts, "open_reports": db.query(SourceReport).filter_by(status="open").count()}


@router.get("")
@router.get("/")
def list_managed_sources(status: str | None = None, current_user=Depends(staff_user), db: Session = Depends(get_db)):
    query = _scope_query(db, current_user)
    if status:
        if status not in {item.value for item in SourceStatus}:
            raise HTTPException(status_code=422, detail="Unknown source status")
        query = query.filter(SourceDocument.status == status)
    documents = query.order_by(SourceDocument.updated_at.desc()).all()
    return {"items": [_staff_document(db, item) for item in documents], "total": len(documents)}


@router.post("/upload", status_code=201)
async def upload_source(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    subject_id: int | None = Form(default=None),
    course_id: int | None = Form(default=None),
    topic_ids: str | None = Form(default=None),
    kind: str = Form(default="material"),
    rights_status: str = Form(default="internal_learning"),
    attribution: str | None = Form(default=None),
    current_user=Depends(staff_user),
    db: Session = Depends(get_db),
):
    selected_topics = _parse_topic_ids(topic_ids)
    _check_taxonomy(db, subject_id, course_id, selected_topics)
    temp_path = await _save_upload(file)
    try:
        result = ingest_source_file(db, temp_path, file.filename or temp_path.name, current_user.id, subject_id=subject_id, course_id=course_id, title=title, kind=kind, publish=False, topics=selected_topics)
        result.document.description = description.strip() if description else None
        result.document.rights_status = rights_status
        result.document.attribution = attribution.strip() if attribution else None
        db.commit()
        db.refresh(result.document)
        return {"document": _staff_document(db, result.document), "deduplicated": result.deduplicated}
    except (ValueError, OSError) as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="This source or version already exists") from error
    finally:
        temp_path.unlink(missing_ok=True)


@router.get("/{source_id}")
def managed_source(source_id: str, current_user=Depends(staff_user), db: Session = Depends(get_db)):
    return _staff_document(db, _owned_document(db, source_id, current_user))


@router.patch("/{source_id}")
def update_source(source_id: str, payload: SourceUpdate, current_user=Depends(staff_user), db: Session = Depends(get_db)):
    document = _owned_document(db, source_id, current_user, lock=True)
    data = payload.model_dump(exclude_unset=True)
    topic_ids = data.pop("topic_ids", None)
    subject_id = data.get("subject_id", document.subject_id)
    course_id = data.get("course_id", document.course_id)
    effective_topics = topic_ids if topic_ids is not None else [topic.id for topic in _topics_for_document(db, document.id)]
    _check_taxonomy(db, subject_id, course_id, effective_topics)
    for field, value in data.items():
        setattr(document, field, value.strip() if isinstance(value, str) else value)
    if topic_ids is not None:
        db.query(SourceDocumentTopic).filter_by(document_id=document.id).delete()
        for index, topic_id in enumerate(topic_ids):
            db.add(SourceDocumentTopic(document_id=document.id, topic_id=topic_id, is_primary=index == 0))
    if _status(document.status) == SourceStatus.PUBLISHED.value:
        _transition_source(db, document, current_user.id, SourceStatus.INBOX.value, "Metadata changed; publication requires review again.")
        document.published_at = None
    db.commit()
    return _staff_document(db, document)


def _topics_for_document(db: Session, document_id: int) -> list[Topic]:
    return db.query(Topic).join(SourceDocumentTopic, SourceDocumentTopic.topic_id == Topic.id).filter(SourceDocumentTopic.document_id == document_id).all()


@router.post("/{source_id}/version", status_code=201)
async def upload_version(
    source_id: str,
    file: UploadFile = File(...),
    notes: str | None = Form(default=None),
    current_user=Depends(staff_user),
    db: Session = Depends(get_db),
):
    document = _owned_document(db, source_id, current_user, lock=True)
    temp_path = await _save_upload(file)
    try:
        result = ingest_source_file(db, temp_path, file.filename or temp_path.name, current_user.id, document=document, topics=())
        result.version.notes = notes.strip() if notes else None
        if _status(document.status) != SourceStatus.INBOX.value:
            _transition_source(db, document, current_user.id, SourceStatus.INBOX.value, "A new immutable version was uploaded.")
        document.reviewed_at = None
        document.published_at = None
        db.commit()
        return {"document": _staff_document(db, document), "deduplicated": result.deduplicated}
    except (ValueError, OSError) as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="This exact version is already attached") from error
    finally:
        temp_path.unlink(missing_ok=True)


@router.post("/{source_id}/review")
def submit_review(source_id: str, payload: WorkflowPayload, current_user=Depends(staff_user), db: Session = Depends(get_db)):
    document = _owned_document(db, source_id, current_user, lock=True)
    if _status(document.status) != SourceStatus.INBOX.value:
        raise HTTPException(status_code=409, detail="Only inbox sources can be submitted for review")
    if not document.subject_id or _latest_version(db, document.id) is None or not _topics_for_document(db, document.id):
        raise HTTPException(status_code=409, detail="Assign a subject, at least one topic, and a file version before review")
    _transition_source(db, document, current_user.id, SourceStatus.REVIEW_PENDING.value, payload.notes)
    db.commit()
    return _staff_document(db, document)


@router.post("/{source_id}/publish")
def publish_source(source_id: str, payload: WorkflowPayload, current_user=Depends(staff_user), db: Session = Depends(get_db)):
    document = _owned_document(db, source_id, current_user, lock=True)
    if _status(document.status) != SourceStatus.REVIEW_PENDING.value:
        raise HTTPException(status_code=409, detail="Only reviewed sources can be published")
    _transition_source(db, document, current_user.id, SourceStatus.PUBLISHED.value, payload.notes)
    document.reviewed_by_id = current_user.id
    document.reviewed_at = datetime.utcnow()
    document.published_at = datetime.utcnow()
    document.archived_at = None
    db.commit()
    return _staff_document(db, document)


@router.post("/{source_id}/archive")
def archive_source(source_id: str, payload: WorkflowPayload, current_user=Depends(staff_user), db: Session = Depends(get_db)):
    document = _owned_document(db, source_id, current_user, lock=True)
    if _status(document.status) == SourceStatus.ARCHIVED.value:
        return _staff_document(db, document)
    _transition_source(db, document, current_user.id, SourceStatus.ARCHIVED.value, payload.notes)
    document.archived_at = datetime.utcnow()
    db.commit()
    return _staff_document(db, document)


@router.post("/{source_id}/restore")
def restore_source(source_id: str, payload: WorkflowPayload, current_user=Depends(staff_user), db: Session = Depends(get_db)):
    document = _owned_document(db, source_id, current_user, lock=True)
    if _status(document.status) != SourceStatus.ARCHIVED.value:
        raise HTTPException(status_code=409, detail="Only archived sources can be restored")
    _transition_source(db, document, current_user.id, SourceStatus.INBOX.value, payload.notes)
    document.archived_at = None
    db.commit()
    return _staff_document(db, document)


@router.get("/{source_id}/reports")
def list_reports(source_id: str, current_user=Depends(staff_user), db: Session = Depends(get_db)):
    document = _owned_document(db, source_id, current_user)
    rows = db.query(SourceReport).filter_by(document_id=document.id).order_by(SourceReport.created_at.desc()).all()
    return [{"id": row.id, "category": row.category, "message": row.message, "status": row.status, "created_at": row.created_at, "resolved_at": row.resolved_at} for row in rows]


@router.post("/{source_id}/reports/{report_id}/resolve")
def resolve_report(source_id: str, report_id: int, payload: ReportResolution, current_user=Depends(staff_user), db: Session = Depends(get_db)):
    document = _owned_document(db, source_id, current_user)
    report = db.query(SourceReport).filter_by(id=report_id, document_id=document.id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Source report not found")
    report.status = payload.status
    report.resolved_by_id = current_user.id
    report.resolved_at = datetime.utcnow()
    db.commit()
    return {"id": report.id, "status": report.status, "resolved_at": report.resolved_at}
