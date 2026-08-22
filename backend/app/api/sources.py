"""Student-facing access to the reviewed, private source library."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    SourceBlob,
    SourceBookmark,
    SourceDocument,
    SourceDocumentTopic,
    SourceReadEvent,
    SourceReadProgress,
    SourceReport,
    SourceStatus,
    SourceVersion,
    Subject,
    Topic,
)
from app.services.source_storage import get_source_storage

router = APIRouter()
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class BookmarkPayload(BaseModel):
    page: int | None = Field(default=None, ge=1)
    note: str | None = Field(default=None, max_length=500)


class ProgressPayload(BaseModel):
    page: int | None = Field(default=None, ge=1)
    progress_percent: float = Field(ge=0, le=100)
    session_id: str | None = Field(default=None, max_length=100)


class ReportPayload(BaseModel):
    category: str = Field(min_length=2, max_length=40)
    message: str = Field(min_length=5, max_length=2000)
    version_id: int | None = None


def _status_value(status: SourceStatus | str) -> str:
    return status.value if isinstance(status, SourceStatus) else str(status)


def _latest_version(db: Session, document_id: int) -> SourceVersion | None:
    return (
        db.query(SourceVersion)
        .filter(SourceVersion.document_id == document_id)
        .order_by(SourceVersion.version_number.desc(), SourceVersion.id.desc())
        .first()
    )


def _document_topics(db: Session, document_id: int) -> list[Topic]:
    return (
        db.query(Topic)
        .join(SourceDocumentTopic, SourceDocumentTopic.topic_id == Topic.id)
        .filter(SourceDocumentTopic.document_id == document_id)
        .order_by(SourceDocumentTopic.is_primary.desc(), Topic.name)
        .all()
    )


def _get_document(db: Session, source_id: str, *, published_only: bool = True) -> SourceDocument:
    query = db.query(SourceDocument)
    if published_only:
        query = query.filter(SourceDocument.status == SourceStatus.PUBLISHED.value)
    document = query.filter(SourceDocument.public_id == source_id).first()
    if document is None and SHA256_PATTERN.fullmatch(source_id.lower()):
        document = (
            query.join(SourceVersion, SourceVersion.document_id == SourceDocument.id)
            .join(SourceBlob, SourceBlob.id == SourceVersion.blob_id)
            .filter(SourceBlob.sha256 == source_id.lower())
            .first()
        )
    if document is None:
        raise HTTPException(status_code=404, detail="Source document not found")
    return document


def _serialize_document(db: Session, document: SourceDocument, user_id: int) -> dict:
    version = _latest_version(db, document.id)
    if version is None:
        raise HTTPException(status_code=404, detail="Source version not found")
    blob = db.query(SourceBlob).filter(SourceBlob.id == version.blob_id).one()
    subject = db.query(Subject).filter(Subject.id == document.subject_id).first() if document.subject_id else None
    topics = _document_topics(db, document.id)
    bookmark = db.query(SourceBookmark).filter_by(user_id=user_id, document_id=document.id).first()
    progress = db.query(SourceReadProgress).filter_by(user_id=user_id, document_id=document.id).first()
    return {
        "id": document.public_id,
        "title": document.title,
        "name": version.original_filename,
        "description": document.description,
        "kind": document.kind,
        "status": _status_value(document.status),
        "extension": blob.extension.lstrip("."),
        "size_bytes": blob.size_bytes,
        "content_type": blob.media_type,
        "subject": {"id": subject.id, "name": subject.name, "slug": subject.slug} if subject else None,
        "topics": [
            {"id": topic.id, "name": topic.name, "slug": topic.slug, "parent_id": topic.parent_id}
            for topic in topics
        ],
        "version": {
            "id": version.id,
            "version_number": version.version_number,
            "page_count": version.page_count,
            "created_at": version.created_at,
        },
        "is_bookmarked": bookmark is not None,
        "bookmark_page": bookmark.page_number if bookmark else None,
        "reading_progress": progress.progress_percent if progress else 0,
        "last_page": progress.last_page if progress else None,
        "last_opened_at": progress.last_opened_at if progress else None,
        "updated_at": document.updated_at,
    }


def _serialize_library(db: Session, documents: list[SourceDocument], user_id: int) -> dict:
    groups: dict[str, dict] = {}
    total_files = 0
    for document in documents:
        try:
            item = _serialize_document(db, document, user_id)
        except HTTPException:
            continue
        subject = item["subject"]
        key = subject["slug"] if subject else "lainnya"
        group = groups.setdefault(
            key,
            {"id": key, "name": subject["name"] if subject else "Lainnya", "files": []},
        )
        group["files"].append(item)
        total_files += 1
    categories = sorted(groups.values(), key=lambda group: group["name"].casefold())
    for category in categories:
        category["files"].sort(key=lambda item: item["title"].casefold())
        category["file_count"] = len(category["files"])
    return {
        "total_documents": total_files,
        "total_files": total_files,
        "total_categories": len(categories),
        "categories": categories,
    }


def _published_query(db: Session):
    return db.query(SourceDocument).filter(SourceDocument.status == SourceStatus.PUBLISHED.value)


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
def list_sources(
    q: str | None = Query(default=None, max_length=200),
    subject_id: int | None = None,
    topic_id: int | None = None,
    file_type: str | None = Query(default=None, max_length=10),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Browse published documents freely across every available subject."""
    query = _published_query(db)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(SourceDocument.title.ilike(pattern), SourceDocument.description.ilike(pattern)))
    if subject_id is not None:
        query = query.filter(SourceDocument.subject_id == subject_id)
    if topic_id is not None:
        query = query.join(SourceDocumentTopic).filter(SourceDocumentTopic.topic_id == topic_id)
    documents = query.order_by(SourceDocument.updated_at.desc(), SourceDocument.id.desc()).all()
    if file_type:
        normalized = file_type.lower().lstrip(".")
        documents = [
            document
            for document in documents
            if (version := _latest_version(db, document.id)) is not None
            and (blob := db.query(SourceBlob).filter_by(id=version.blob_id).first()) is not None
            and blob.extension.lower().lstrip(".") == normalized
        ]
    return _serialize_library(db, documents, current_user.id)


@router.get("/me/bookmarks")
def list_bookmarks(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    document_ids = [
        row.document_id
        for row in db.query(SourceBookmark)
        .filter(SourceBookmark.user_id == current_user.id)
        .order_by(SourceBookmark.created_at.desc())
        .all()
    ]
    documents = _published_query(db).filter(SourceDocument.id.in_(document_ids)).all() if document_ids else []
    order = {document_id: index for index, document_id in enumerate(document_ids)}
    documents.sort(key=lambda document: order.get(document.id, len(order)))
    return _serialize_library(db, documents, current_user.id)


@router.get("/me/history")
def list_history(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(SourceReadProgress)
        .filter(SourceReadProgress.user_id == current_user.id)
        .order_by(SourceReadProgress.last_opened_at.desc())
        .limit(50)
        .all()
    )
    ids = [row.document_id for row in rows]
    documents = _published_query(db).filter(SourceDocument.id.in_(ids)).all() if ids else []
    order = {document_id: index for index, document_id in enumerate(ids)}
    documents.sort(key=lambda document: order.get(document.id, len(order)))
    return _serialize_library(db, documents, current_user.id)


@router.get("/{source_id}/content")
def get_source_content(
    source_id: str,
    version_id: int | None = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream a private source after authentication; storage paths never enter the URL."""
    document = _get_document(db, source_id)
    version_query = db.query(SourceVersion).filter(SourceVersion.document_id == document.id)
    version = (
        version_query.filter(SourceVersion.id == version_id).first()
        if version_id is not None
        else version_query.order_by(SourceVersion.version_number.desc(), SourceVersion.id.desc()).first()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Source version not found")
    blob = db.query(SourceBlob).filter(SourceBlob.id == version.blob_id).first()
    if blob is None:
        raise HTTPException(status_code=404, detail="Source content not found")
    storage = get_source_storage(blob.storage_backend)
    if not storage.exists(blob.storage_key):
        raise HTTPException(status_code=404, detail="Source content is unavailable")

    db.add(SourceReadEvent(user_id=current_user.id, document_id=document.id, source_version_id=version.id, event_type="opened", page_number=None))
    progress = db.query(SourceReadProgress).filter_by(user_id=current_user.id, document_id=document.id).first()
    if progress is None:
        db.add(SourceReadProgress(user_id=current_user.id, document_id=document.id, source_version_id=version.id, progress_percent=0, last_opened_at=datetime.utcnow()))
    else:
        progress.source_version_id = version.id
        progress.last_opened_at = datetime.utcnow()
    db.commit()

    headers = {
        "Cache-Control": "private, max-age=300",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data: blob:",
    }
    local_path = storage.local_path(blob.storage_key)
    if local_path is not None:
        return FileResponse(path=local_path, media_type=blob.media_type, filename=Path(version.original_filename).name, content_disposition_type="inline", headers=headers)

    safe_name = Path(version.original_filename.replace("\r", "").replace("\n", "")).name

    def stream_chunks() -> Iterator[bytes]:
        with storage.open(blob.storage_key) as stream:
            while chunk := stream.read(1024 * 1024):
                yield chunk

    headers["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(safe_name)}"
    return StreamingResponse(stream_chunks(), media_type=blob.media_type, headers=headers)


@router.get("/{source_id}")
def get_source_metadata(source_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    document = _get_document(db, source_id)
    return _serialize_document(db, document, current_user.id)


@router.put("/{source_id}/bookmark")
def save_bookmark(source_id: str, payload: BookmarkPayload, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    document = _get_document(db, source_id)
    version = _latest_version(db, document.id)
    if version is None:
        raise HTTPException(status_code=404, detail="Source version not found")
    bookmark = db.query(SourceBookmark).filter_by(user_id=current_user.id, document_id=document.id).first()
    if bookmark is None:
        bookmark = SourceBookmark(user_id=current_user.id, document_id=document.id)
        db.add(bookmark)
    bookmark.source_version_id = version.id
    bookmark.page_number = payload.page
    bookmark.note = payload.note.strip() if payload.note else None
    db.commit()
    return {"bookmarked": True, "page": bookmark.page_number, "note": bookmark.note}


@router.delete("/{source_id}/bookmark")
def delete_bookmark(source_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    document = _get_document(db, source_id)
    bookmark = db.query(SourceBookmark).filter_by(user_id=current_user.id, document_id=document.id).first()
    if bookmark is not None:
        db.delete(bookmark)
        db.commit()
    return {"bookmarked": False}


@router.put("/{source_id}/progress")
def update_progress(source_id: str, payload: ProgressPayload, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    document = _get_document(db, source_id)
    version = _latest_version(db, document.id)
    if version is None:
        raise HTTPException(status_code=404, detail="Source version not found")
    progress = db.query(SourceReadProgress).filter_by(user_id=current_user.id, document_id=document.id).first()
    if progress is None:
        progress = SourceReadProgress(user_id=current_user.id, document_id=document.id)
        db.add(progress)
    progress.source_version_id = version.id
    progress.last_page = payload.page
    progress.progress_percent = payload.progress_percent
    progress.last_opened_at = datetime.utcnow()
    db.add(SourceReadEvent(user_id=current_user.id, document_id=document.id, source_version_id=version.id, event_type="page", page_number=payload.page, session_id=payload.session_id))
    db.commit()
    return {"last_page": progress.last_page, "progress_percent": progress.progress_percent, "updated_at": progress.updated_at}


@router.post("/{source_id}/reports", status_code=201)
def report_source(source_id: str, payload: ReportPayload, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    document = _get_document(db, source_id)
    version = _latest_version(db, document.id)
    if payload.version_id is not None:
        version = db.query(SourceVersion).filter_by(id=payload.version_id, document_id=document.id).first()
    report = SourceReport(user_id=current_user.id, document_id=document.id, source_version_id=version.id if version else None, category=payload.category.strip().lower(), message=payload.message.strip())
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "status": report.status, "created_at": report.created_at}
