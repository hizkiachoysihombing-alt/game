import csv
import hashlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import sources
from app.core.security import get_current_user


@pytest.fixture()
def source_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, bytes, str]:
    root = tmp_path / "source_materials"
    document = root / "00_INBOX" / "batch-1" / "fisika-dasar" / "Materi Fisika.pdf"
    document.parent.mkdir(parents=True)
    payload = b"%PDF-1.4\nprivate learning source\n"
    document.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()

    manifest_root = root / "manifests"
    manifest_root.mkdir()
    fields = [
        "batch_id",
        "category",
        "file_name",
        "relative_path",
        "extension",
        "bytes",
        "sha256",
        "ingestion_status",
        "review_status",
        "source_archive",
    ]
    rows = [
        {
            "batch_id": "batch-1",
            "category": "fisika-dasar",
            "file_name": document.name,
            "relative_path": "00_INBOX/batch-1/fisika-dasar/Materi Fisika.pdf",
            "extension": ".pdf",
            "bytes": str(len(payload)),
            "sha256": digest,
            "ingestion_status": "new",
            "review_status": "pending",
            "source_archive": "private.zip",
        },
        {
            "batch_id": "batch-1",
            "category": "fisika-dasar",
            "file_name": "secret.pdf",
            "relative_path": "../secret.pdf",
            "extension": ".pdf",
            "bytes": "1",
            "sha256": "0" * 64,
            "ingestion_status": "new",
            "review_status": "pending",
            "source_archive": "private.zip",
        },
    ]
    with (manifest_root / "batch-1.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    (root / "unlisted.pdf").write_bytes(b"not in manifest")
    monkeypatch.setattr(sources, "SOURCE_ROOT", root)
    sources._load_records_cached.cache_clear()
    yield root, payload, digest
    sources._load_records_cached.cache_clear()


@pytest.fixture()
def client(source_root: tuple[Path, bytes, str]) -> TestClient:
    app = FastAPI()
    app.include_router(sources.router, prefix="/api/sources")
    app.dependency_overrides[get_current_user] = lambda: {"id": 1}
    return TestClient(app)


def test_source_library_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(sources.router, prefix="/api/sources")
    with TestClient(app) as unauthenticated_client:
        assert unauthenticated_client.get("/api/sources").status_code == 401


def test_source_library_lists_only_valid_manifest_files(
    client: TestClient,
    source_root: tuple[Path, bytes, str],
) -> None:
    response = client.get("/api/sources")
    assert response.status_code == 200
    body = response.json()
    assert body["total_categories"] == 1
    assert body["total_files"] == 1
    assert body["categories"][0]["name"] == "Fisika Dasar"
    assert body["categories"][0]["file_count"] == 1
    public_file = body["categories"][0]["files"][0]
    assert public_file["name"] == "Materi Fisika.pdf"
    assert not {"relative_path", "source_archive", "batch_id", "_path"}.intersection(
        public_file
    )


def test_source_download_uses_id_and_preserves_integrity(
    client: TestClient,
    source_root: tuple[Path, bytes, str],
) -> None:
    _, payload, digest = source_root
    response = client.get(f"/api/sources/{digest}?download=true")
    assert response.status_code == 200
    assert response.content == payload
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "attachment" in response.headers["content-disposition"]


@pytest.mark.parametrize(
    "source_id",
    ["not-a-hash", "..%5Csecret.pdf", "0" * 64],
)
def test_unknown_or_path_like_source_ids_are_not_downloadable(
    client: TestClient,
    source_id: str,
) -> None:
    assert client.get(f"/api/sources/{source_id}").status_code == 404


@pytest.mark.parametrize(
    "relative_path",
    [
        "../secret.pdf",
        "..\\secret.pdf",
        "/etc/passwd",
        "C:/secret.pdf",
        "//server/share/secret.pdf",
        "document.pdf:stream",
    ],
)
def test_windows_and_posix_traversal_paths_are_rejected(
    source_root: tuple[Path, bytes, str],
    relative_path: str,
) -> None:
    assert sources._safe_source_path(relative_path) is None
