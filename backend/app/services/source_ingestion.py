"""Validation, deduplication, versioning, and legacy import for source files."""

from __future__ import annotations

import csv
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    SourceBlob,
    SourceDocument,
    SourceDocumentTopic,
    SourceStatus,
    SourceVersion,
    SourceWorkflowEvent,
    Subject,
    Topic,
)
from app.services.source_storage import (
    SourceStorage,
    get_source_storage,
    hash_file,
    normalize_extension,
)


SOURCE_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
LEGACY_CATEGORY_SUBJECT_SLUGS = {
    "basis-data": "database-fundamentals",
    "fisika-dasar": "basic-physics",
    "kimia-dasar": "basic-chemistry",
    "matematika-teknik": "engineering-mathematics",
    "sistem-digital": "digital-electronics",
}


class SourceValidationError(ValueError):
    """Raised when a source upload does not meet the private-library contract."""


@dataclass(frozen=True)
class ValidatedSource:
    path: Path
    original_filename: str
    extension: str
    media_type: str
    size_bytes: int
    sha256: str
    page_count: int | None


@dataclass(frozen=True)
class IngestionResult:
    document: SourceDocument
    version: SourceVersion
    blob: SourceBlob
    deduplicated: bool


@dataclass(frozen=True)
class LegacyImportResult:
    imported: int
    deduplicated: int
    skipped: int
    errors: tuple[str, ...]


def _safe_original_filename(filename: str) -> str:
    value = filename.strip()
    if (
        not value
        or len(value) > 512
        or any(character in value for character in ("\x00", "\r", "\n", ":"))
        or PurePosixPath(value).name != value
        or PureWindowsPath(value).name != value
    ):
        raise SourceValidationError("Invalid source filename")
    return value


def _validate_signature(path: Path, extension: str) -> None:
    with path.open("rb") as handle:
        header = handle.read(1024)

    if extension == ".pdf" and b"%PDF-" not in header:
        raise SourceValidationError("The uploaded file is not a valid PDF")
    if extension == ".doc" and not header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise SourceValidationError("The uploaded file is not a valid legacy Word document")
    if extension == ".docx":
        if not header.startswith(b"PK"):
            raise SourceValidationError("The uploaded file is not a valid DOCX document")
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise SourceValidationError("The uploaded archive is not a DOCX document")
                total_uncompressed = sum(item.file_size for item in archive.infolist())
                if total_uncompressed > max(settings.SOURCE_MAX_UPLOAD_BYTES * 10, 250 * 1024 * 1024):
                    raise SourceValidationError("The DOCX expands beyond the safe processing limit")
        except zipfile.BadZipFile as error:
            raise SourceValidationError("The uploaded file is not a valid DOCX document") from error


def _pdf_page_count(path: Path) -> int | None:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        # Encryption or non-standard PDFs can still be delivered safely; page
        # metadata can be populated later by the conversion/indexing worker.
        return None


def validate_source_file(
    path: Path,
    original_filename: str,
    declared_content_type: str | None = None,
) -> ValidatedSource:
    """Validate an upload by size, extension, signature, and content hash."""

    del declared_content_type  # Browser declarations are advisory, never trusted.
    source_path = Path(path)
    if not source_path.is_file() or source_path.is_symlink():
        raise SourceValidationError("Source upload must be a regular file")

    filename = _safe_original_filename(original_filename)
    extension = normalize_extension(Path(filename).suffix)
    size_bytes = source_path.stat().st_size
    if size_bytes <= 0:
        raise SourceValidationError("Source upload is empty")
    if size_bytes > settings.SOURCE_MAX_UPLOAD_BYTES:
        raise SourceValidationError("Source upload exceeds the configured size limit")

    _validate_signature(source_path, extension)
    digest = hash_file(source_path)
    return ValidatedSource(
        path=source_path,
        original_filename=filename,
        extension=extension,
        media_type=SOURCE_MEDIA_TYPES[extension],
        size_bytes=size_bytes,
        sha256=digest,
        page_count=_pdf_page_count(source_path) if extension == ".pdf" else None,
    )


def _assign_topics(
    db: Session, document: SourceDocument, topic_ids: Iterable[int]
) -> None:
    ordered_ids = list(dict.fromkeys(int(topic_id) for topic_id in topic_ids))
    if not ordered_ids:
        return
    valid_ids = {
        topic_id
        for (topic_id,) in db.query(Topic.id).filter(Topic.id.in_(ordered_ids)).all()
    }
    if valid_ids != set(ordered_ids):
        raise SourceValidationError("One or more source topics do not exist")

    existing_ids = {link.topic_id for link in document.topic_links}
    for index, topic_id in enumerate(ordered_ids):
        if topic_id not in existing_ids:
            document.topic_links.append(
                SourceDocumentTopic(topic_id=topic_id, is_primary=index == 0)
            )


def ingest_source_file(
    db: Session,
    source_path: Path,
    original_filename: str,
    uploaded_by_id: int | None,
    document: SourceDocument | None = None,
    subject_id: int | None = None,
    course_id: int | None = None,
    title: str | None = None,
    kind: str = "material",
    publish: bool = False,
    topics: Iterable[int] = (),
    *,
    description: str | None = None,
    rights_status: str = "internal_learning",
    attribution: str | None = None,
    notes: str | None = None,
    declared_content_type: str | None = None,
    storage: SourceStorage | None = None,
) -> IngestionResult:
    """Store one validated upload and add an immutable logical document version.

    The function flushes but does not commit; the API or worker owns the database
    transaction. Physical blobs are deduplicated globally by SHA-256.
    """

    validated = validate_source_file(source_path, original_filename, declared_content_type)
    selected_storage = storage or get_source_storage()
    blob = db.query(SourceBlob).filter(SourceBlob.sha256 == validated.sha256).first()
    deduplicated = blob is not None
    if blob is not None:
        blob_storage = (
            selected_storage
            if blob.storage_backend == selected_storage.backend_name
            else get_source_storage(blob.storage_backend)
        )
        if not blob_storage.exists(blob.storage_key):
            raise SourceValidationError("Deduplicated source content is missing from storage")
    else:
        storage_key = selected_storage.put_file(
            validated.path,
            sha256=validated.sha256,
            extension=validated.extension,
            media_type=validated.media_type,
        )
        blob = SourceBlob(
            sha256=validated.sha256,
            size_bytes=validated.size_bytes,
            media_type=validated.media_type,
            extension=validated.extension,
            storage_backend=selected_storage.backend_name,
            storage_key=storage_key,
        )
        db.add(blob)
        db.flush()

    now = datetime.utcnow()
    if document is None:
        normalized_title = (title or Path(validated.original_filename).stem).strip()
        if not normalized_title:
            raise SourceValidationError("Source title is required")
        target_status = SourceStatus.PUBLISHED.value if publish else SourceStatus.INBOX.value
        document = SourceDocument(
            subject_id=subject_id,
            course_id=course_id,
            title=normalized_title,
            description=description,
            kind=(kind or "material").strip(),
            rights_status=(rights_status or "internal_learning").strip(),
            attribution=attribution,
            status=target_status,
            created_by_id=uploaded_by_id,
            reviewed_by_id=uploaded_by_id if publish else None,
            reviewed_at=now if publish else None,
            published_at=now if publish else None,
        )
        db.add(document)
        db.flush()
        db.add(
            SourceWorkflowEvent(
                document_id=document.id,
                actor_id=uploaded_by_id,
                from_status=None,
                to_status=target_status,
                notes="Imported as a published legacy source" if publish else "Uploaded to inbox",
            )
        )
    else:
        document = (
            db.query(SourceDocument)
            .filter(SourceDocument.id == document.id)
            .with_for_update()
            .one()
        )
        existing_version = (
            db.query(SourceVersion)
            .filter(
                SourceVersion.document_id == document.id,
                SourceVersion.blob_id == blob.id,
            )
            .first()
        )
        if existing_version is not None:
            return IngestionResult(document, existing_version, blob, True)

    next_version = (
        db.query(func.coalesce(func.max(SourceVersion.version_number), 0))
        .filter(SourceVersion.document_id == document.id)
        .scalar()
        + 1
    )
    version = SourceVersion(
        document_id=document.id,
        blob_id=blob.id,
        version_number=next_version,
        original_filename=validated.original_filename,
        page_count=validated.page_count,
        uploaded_by_id=uploaded_by_id,
        notes=notes,
    )
    db.add(version)
    _assign_topics(db, document, topics)
    db.flush()
    return IngestionResult(document, version, blob, deduplicated)


def _safe_legacy_path(root: Path, relative_path: str) -> Path | None:
    value = relative_path.strip()
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if (
        not value
        or any(character in value for character in ("\x00", "\r", "\n", "\\", ":"))
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        return None
    try:
        candidate = (root / Path(*posix_path.parts)).resolve(strict=True)
        candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate if candidate.is_file() else None


def import_legacy_manifest(
    db: Session,
    manifest_path: Path,
    created_by_id: int | None,
    category_subject_slugs: dict[str, str] | None = None,
    *,
    storage: SourceStorage | None = None,
) -> LegacyImportResult:
    """Idempotently import the original private CSV catalog as published sources."""

    manifest = Path(manifest_path).resolve(strict=True)
    source_root = manifest.parent.parent.resolve(strict=True)
    category_map = category_subject_slugs or LEGACY_CATEGORY_SUBJECT_SLUGS
    selected_storage = storage or get_source_storage()
    imported = deduplicated = skipped = 0
    errors: list[str] = []

    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            filename = (row.get("file_name") or "").strip()
            try:
                expected_digest = (row.get("sha256") or "").strip().lower()
                if not SHA256_PATTERN.fullmatch(expected_digest):
                    raise SourceValidationError("Manifest SHA-256 is invalid")
                source_path = _safe_legacy_path(
                    source_root, (row.get("relative_path") or "").strip()
                )
                if source_path is None:
                    raise SourceValidationError("Manifest source path is invalid")
                if hash_file(source_path) != expected_digest:
                    raise SourceValidationError("Manifest source hash does not match")

                existing_version = (
                    db.query(SourceVersion)
                    .join(SourceBlob, SourceBlob.id == SourceVersion.blob_id)
                    .filter(SourceBlob.sha256 == expected_digest)
                    .first()
                )
                if existing_version is not None:
                    skipped += 1
                    continue

                category = (row.get("category") or "").strip()
                subject_slug = category_map.get(category)
                subject = (
                    db.query(Subject).filter(Subject.slug == subject_slug).first()
                    if subject_slug
                    else None
                )
                archive_name = (row.get("source_archive") or "legacy source archive").strip()
                with db.begin_nested():
                    result = ingest_source_file(
                        db,
                        source_path,
                        filename,
                        created_by_id,
                        subject_id=subject.id if subject else None,
                        title=Path(filename).stem,
                        kind="assessment" if re.search(r"\b(uts|uas|kuis|quiz|soal|pr)\b", filename, re.I) else "material",
                        publish=True,
                        attribution=f"Imported from {archive_name}",
                        storage=selected_storage,
                    )
                imported += 1
                if result.deduplicated:
                    deduplicated += 1
            except (OSError, csv.Error, SourceValidationError, ValueError) as error:
                errors.append(f"row {row_number} ({filename or 'unnamed'}): {error}")

    return LegacyImportResult(imported, deduplicated, skipped, tuple(errors))
