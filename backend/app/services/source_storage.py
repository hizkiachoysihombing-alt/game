"""Private, content-addressed storage for immutable learning-source blobs."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

from app.core.config import settings


ALLOWED_SOURCE_EXTENSIONS = frozenset({".pdf", ".doc", ".docx"})
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
STORAGE_KEY_PATTERN = re.compile(
    r"^blobs/(?P<prefix>[0-9a-f]{2})/(?P<digest>[0-9a-f]{64})(?P<extension>\.pdf|\.doc|\.docx)$"
)


class SourceStorageError(RuntimeError):
    """Base exception for source-storage failures."""


class InvalidStorageKey(SourceStorageError):
    """Raised when a key is not a canonical content-addressed source key."""


class SourceStorage(Protocol):
    """Storage contract used by ingestion and authenticated content delivery."""

    backend_name: str

    def put_file(
        self,
        source_path: Path,
        *,
        sha256: str,
        extension: str,
        media_type: str,
    ) -> str:
        """Persist a validated file and return its immutable storage key."""

    def open(self, storage_key: str) -> BinaryIO:
        """Open an existing object as a binary stream."""

    def exists(self, storage_key: str) -> bool:
        """Return whether an immutable object exists."""

    def local_path(self, storage_key: str) -> Path | None:
        """Return a safe local path when available, otherwise ``None``."""


def normalize_extension(extension: str) -> str:
    normalized = extension.strip().lower()
    if normalized and not normalized.startswith("."):
        normalized = f".{normalized}"
    if normalized not in ALLOWED_SOURCE_EXTENSIONS:
        raise SourceStorageError(f"Unsupported source extension: {extension!r}")
    return normalized


def build_storage_key(sha256: str, extension: str) -> str:
    digest = sha256.strip().lower()
    if not SHA256_PATTERN.fullmatch(digest):
        raise SourceStorageError("Invalid SHA-256 digest")
    normalized_extension = normalize_extension(extension)
    return f"blobs/{digest[:2]}/{digest}{normalized_extension}"


def validate_storage_key(storage_key: str) -> str:
    value = storage_key.strip()
    match = STORAGE_KEY_PATTERN.fullmatch(value)
    posix_path = PurePosixPath(value)
    if (
        match is None
        or posix_path.is_absolute()
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or match.group("prefix") != match.group("digest")[:2]
    ):
        raise InvalidStorageKey("Invalid source storage key")
    return value


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class LocalSourceStorage:
    """Private local filesystem storage rooted below one configured directory."""

    backend_name = "local"

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, storage_key: str) -> Path:
        key = validate_storage_key(storage_key)
        candidate = (self.root / Path(*PurePosixPath(key).parts)).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as error:
            raise InvalidStorageKey("Storage key escapes the configured root") from error
        return candidate

    def put_file(
        self,
        source_path: Path,
        *,
        sha256: str,
        extension: str,
        media_type: str,
    ) -> str:
        del media_type  # Retained in SourceBlob metadata; the filesystem needs no sidecar.
        source = Path(source_path)
        if not source.is_file():
            raise SourceStorageError("Source upload is not a regular file")

        storage_key = build_storage_key(sha256, extension)
        destination = self._path(storage_key)
        if destination.is_file():
            if hash_file(destination) != sha256.lower():
                raise SourceStorageError("Existing immutable object failed its hash check")
            return storage_key

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with source.open("rb") as input_handle, tempfile.NamedTemporaryFile(
                mode="wb", prefix=".source-", suffix=".tmp", dir=destination.parent, delete=False
            ) as output_handle:
                temporary_name = output_handle.name
                digest = hashlib.sha256()
                for block in iter(lambda: input_handle.read(1024 * 1024), b""):
                    digest.update(block)
                    output_handle.write(block)
                output_handle.flush()
                os.fsync(output_handle.fileno())

            if digest.hexdigest() != sha256.lower():
                raise SourceStorageError("Source changed while it was being stored")
            os.replace(temporary_name, destination)
            temporary_name = None
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)
        return storage_key

    def open(self, storage_key: str) -> BinaryIO:
        path = self._path(storage_key)
        if not path.is_file():
            raise FileNotFoundError(storage_key)
        return path.open("rb")

    def exists(self, storage_key: str) -> bool:
        return self._path(storage_key).is_file()

    def local_path(self, storage_key: str) -> Path | None:
        path = self._path(storage_key)
        return path if path.is_file() else None


class S3SourceStorage:
    """S3-compatible private object storage (AWS S3, Cloudflare R2, or MinIO)."""

    backend_name = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str = "",
        region: str = "auto",
        access_key: str = "",
        secret_key: str = "",
        force_path_style: bool = False,
        server_side_encryption: str = "",
    ):
        if not bucket:
            raise SourceStorageError("S3_BUCKET is required for S3 source storage")
        try:
            import boto3
            from botocore.config import Config
            from botocore.exceptions import ClientError
        except ImportError as error:  # pragma: no cover - dependency is optional at runtime
            raise SourceStorageError("boto3 is required for S3 source storage") from error

        client_options: dict[str, object] = {
            "region_name": region or None,
            "config": Config(
                s3={"addressing_style": "path" if force_path_style else "auto"}
            ),
        }
        if endpoint_url:
            client_options["endpoint_url"] = endpoint_url
        if access_key:
            client_options["aws_access_key_id"] = access_key
        if secret_key:
            client_options["aws_secret_access_key"] = secret_key

        self.bucket = bucket
        self.server_side_encryption = server_side_encryption
        self.client = boto3.client("s3", **client_options)
        self._client_error = ClientError

    def put_file(
        self,
        source_path: Path,
        *,
        sha256: str,
        extension: str,
        media_type: str,
    ) -> str:
        source = Path(source_path)
        if not source.is_file():
            raise SourceStorageError("Source upload is not a regular file")
        if hash_file(source) != sha256.lower():
            raise SourceStorageError("Source failed its hash check before upload")

        storage_key = build_storage_key(sha256, extension)
        existing = self._head_object(storage_key)
        if existing is not None:
            metadata_digest = (existing.get("Metadata") or {}).get("sha256", "").lower()
            if (
                int(existing.get("ContentLength", -1)) != source.stat().st_size
                or metadata_digest != sha256.lower()
            ):
                raise SourceStorageError("Existing immutable S3 object failed its metadata check")
            return storage_key

        extra_args: dict[str, object] = {
            "ContentType": media_type,
            "Metadata": {"sha256": sha256.lower()},
        }
        if self.server_side_encryption:
            extra_args["ServerSideEncryption"] = self.server_side_encryption
        self.client.upload_file(
            str(source), self.bucket, storage_key, ExtraArgs=extra_args
        )
        return storage_key

    def open(self, storage_key: str) -> BinaryIO:
        key = validate_storage_key(storage_key)
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"]

    def exists(self, storage_key: str) -> bool:
        return self._head_object(storage_key) is not None

    def _head_object(self, storage_key: str) -> dict[str, object] | None:
        key = validate_storage_key(storage_key)
        try:
            return self.client.head_object(Bucket=self.bucket, Key=key)
        except self._client_error as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise SourceStorageError("Could not inspect S3 source object") from error

    def local_path(self, storage_key: str) -> Path | None:
        validate_storage_key(storage_key)
        return None


@lru_cache(maxsize=2)
def get_source_storage(backend_name: str | None = None) -> SourceStorage:
    """Build a configured backend once per process.

    ``backend_name`` lets content delivery keep reading older local blobs after
    new uploads have switched to S3 (or vice versa).
    """

    backend = (backend_name or settings.SOURCE_STORAGE_BACKEND).strip().lower()
    if backend == "local":
        return LocalSourceStorage(settings.SOURCE_LOCAL_ROOT)
    if backend == "s3":
        return S3SourceStorage(
            bucket=settings.S3_BUCKET,
            endpoint_url=settings.S3_ENDPOINT_URL,
            region=settings.S3_REGION,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            force_path_style=settings.S3_FORCE_PATH_STYLE,
            server_side_encryption=settings.S3_SERVER_SIDE_ENCRYPTION,
        )
    raise SourceStorageError(f"Unsupported SOURCE_STORAGE_BACKEND: {backend!r}")
