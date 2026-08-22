"""Authenticated access to private, manifest-listed learning sources."""

from __future__ import annotations

import csv
import hashlib
import os
import re
from functools import lru_cache
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.security import get_current_user

router = APIRouter()

DEFAULT_SOURCE_ROOT = Path(__file__).resolve().parents[3] / "source_materials"
SOURCE_ROOT = Path(
    os.getenv("SOURCE_MATERIALS_ROOT")
    or os.getenv("SOURCE_MATERIALS_DIR")
    or DEFAULT_SOURCE_ROOT
).resolve()
ALLOWED_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
CATEGORY_LABELS = {
    "fisika-dasar": "Fisika Dasar",
    "kimia-dasar": "Kimia Dasar",
    "basis-data": "Basis Data",
    "sistem-digital": "Sistem Digital",
    "matematika-teknik": "Matematika Teknik",
    "belum-terklasifikasi": "Belum Terklasifikasi",
}
CATEGORY_ORDER = {key: index for index, key in enumerate(CATEGORY_LABELS)}


def _safe_source_path(relative_path: str) -> Path | None:
    """Resolve only simple POSIX manifest paths that stay below SOURCE_ROOT."""
    value = relative_path.strip()
    if not value or any(character in value for character in ("\x00", "\r", "\n", "\\", ":")):
        return None

    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    raw_parts = value.split("/")
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or windows_path.root
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        return None

    try:
        root = SOURCE_ROOT.resolve(strict=True)
        candidate = (root / Path(*posix_path.parts)).resolve(strict=True)
    except (OSError, RuntimeError):
        return None

    try:
        candidate.relative_to(root)
    except ValueError:
        return None

    if not candidate.is_file() or candidate.suffix.lower() not in ALLOWED_CONTENT_TYPES:
        return None
    if any(character in candidate.name for character in ("\r", "\n")):
        return None
    return candidate


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_files() -> list[Path]:
    manifest_root = SOURCE_ROOT / "manifests"
    if not manifest_root.is_dir():
        return []
    return sorted(manifest_root.glob("*.csv"))


def _catalog_signature() -> tuple[Any, ...]:
    """Track manifests and listed files so newly added batches appear automatically."""
    signature: list[Any] = [str(SOURCE_ROOT)]
    for manifest in _manifest_files():
        try:
            manifest_stat = manifest.stat()
            signature.append((str(manifest), manifest_stat.st_mtime_ns, manifest_stat.st_size))
            with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    source_path = _safe_source_path((row.get("relative_path") or "").strip())
                    if source_path is not None:
                        source_stat = source_path.stat()
                        signature.append(
                            (str(source_path), source_stat.st_mtime_ns, source_stat.st_size)
                        )
        except (OSError, csv.Error, UnicodeError):
            signature.append((str(manifest), "unreadable"))
    return tuple(signature)


@lru_cache(maxsize=2)
def _load_records_cached(signature: tuple[Any, ...]) -> tuple[dict[str, Any], ...]:
    del signature  # The value is the cache key; records are read from the current root.
    records: dict[str, dict[str, Any]] = {}

    for manifest in _manifest_files():
        try:
            with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    digest = (row.get("sha256") or "").strip().lower()
                    relative_path = (row.get("relative_path") or "").strip()
                    source_path = _safe_source_path(relative_path)
                    if not SHA256_PATTERN.fullmatch(digest) or source_path is None:
                        continue

                    manifest_extension = (row.get("extension") or "").strip().lower()
                    manifest_name = (row.get("file_name") or "").strip()
                    if (
                        manifest_extension != source_path.suffix.lower()
                        or manifest_name != source_path.name
                        or any(character in manifest_name for character in ("\r", "\n"))
                    ):
                        continue

                    try:
                        manifest_size = int((row.get("bytes") or "").strip())
                    except ValueError:
                        continue
                    actual_size = source_path.stat().st_size
                    if manifest_size != actual_size or _hash_file(source_path) != digest:
                        continue

                    category = (row.get("category") or "belum-terklasifikasi").strip()
                    records.setdefault(
                        digest,
                        {
                            "id": digest,
                            "name": source_path.name,
                            "category": category,
                            "category_label": CATEGORY_LABELS.get(
                                category, category.replace("-", " ").title()
                            ),
                            "extension": source_path.suffix.lower().lstrip("."),
                            "size_bytes": actual_size,
                            "content_type": ALLOWED_CONTENT_TYPES[source_path.suffix.lower()],
                            "_path": source_path,
                        },
                    )
        except (OSError, csv.Error, UnicodeError):
            continue

    return tuple(
        sorted(
            records.values(),
            key=lambda item: (
                CATEGORY_ORDER.get(item["category"], 999),
                item["category_label"].casefold(),
                item["name"].casefold(),
            ),
        )
    )


def _load_records() -> tuple[dict[str, Any], ...]:
    return _load_records_cached(_catalog_signature())


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "name": record["name"],
        "extension": record["extension"],
        "size_bytes": record["size_bytes"],
        "content_type": record["content_type"],
    }


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
def list_sources(current_user=Depends(get_current_user)):
    """List source documents grouped by their reviewed subject category."""
    del current_user
    records = _load_records()
    groups: dict[str, dict[str, Any]] = {}
    for record in records:
        category = record["category"]
        group = groups.setdefault(
            category,
            {"id": category, "name": record["category_label"], "files": []},
        )
        group["files"].append(_public_record(record))

    categories = sorted(
        groups.values(),
        key=lambda group: (CATEGORY_ORDER.get(group["id"], 999), group["name"].casefold()),
    )
    for category in categories:
        category["file_count"] = len(category["files"])
    return {"total_files": len(records), "total_categories": len(categories), "categories": categories}


@router.get("/{source_id}")
def get_source_file(
    source_id: str,
    download: bool = Query(default=False),
    current_user=Depends(get_current_user),
):
    """Open or download one source file selected by its manifest SHA-256."""
    del current_user
    normalized_id = source_id.lower()
    if not SHA256_PATTERN.fullmatch(normalized_id):
        raise HTTPException(status_code=404, detail="Source file not found")

    record = next((item for item in _load_records() if item["id"] == normalized_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Source file not found")

    source_path: Path = record["_path"]
    try:
        if source_path.stat().st_size != record["size_bytes"] or _hash_file(source_path) != normalized_id:
            raise HTTPException(status_code=404, detail="Source file not found")
    except OSError as error:
        raise HTTPException(status_code=404, detail="Source file not found") from error

    response = FileResponse(
        source_path,
        media_type=record["content_type"],
        filename=record["name"],
        content_disposition_type="attachment" if download else "inline",
    )
    response.headers["Cache-Control"] = "private, max-age=300"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
