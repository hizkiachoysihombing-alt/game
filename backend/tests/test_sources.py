from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import source_management, sources
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.permissions import UserRole
from app.core.security import get_current_user
from app.models.models import (
    Question,
    QuestionBank,
    QuestionDifficulty,
    QuestionSourceCitation,
    QuestionType,
    QuestionWorkflowStatus,
    SourceBlob,
    SourceDocument,
    SourceReadEvent,
    SourceReport,
    SourceStatus,
    Subject,
    Topic,
    User,
)
from app.services.source_ingestion import ingest_source_file
from app.services.source_storage import get_source_storage


PDF_ONE = b"%PDF-1.4\n% ElectroQuest source one\n%%EOF\n"
PDF_TWO = b"%PDF-1.4\n% ElectroQuest source two\n%%EOF\n"
PDF_UPLOAD = b"%PDF-1.4\n% ElectroQuest staff upload\n%%EOF\n"
PDF_NEW_VERSION = b"%PDF-1.4\n% ElectroQuest replacement version\n%%EOF\n"


@pytest.fixture()
def source_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "source-api.sqlite"
    storage_root = tmp_path / "private-storage"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    monkeypatch.setattr(settings, "SOURCE_STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "SOURCE_LOCAL_ROOT", str(storage_root))
    monkeypatch.setattr(settings, "SOURCE_MAX_UPLOAD_BYTES", 1024 * 1024)
    get_source_storage.cache_clear()

    first_pdf = tmp_path / "published.pdf"
    second_pdf = tmp_path / "draft.pdf"
    first_pdf.write_bytes(PDF_ONE)
    second_pdf.write_bytes(PDF_TWO)

    with SessionLocal() as db:
        student = User(
            email="source-student@example.test",
            username="source-student",
            hashed_password="not-used",
            full_name="Source Student",
            role=UserRole.STUDENT,
            is_active=True,
        )
        instructor = User(
            email="source-instructor@example.test",
            username="source-instructor",
            hashed_password="not-used",
            full_name="Source Instructor",
            role=UserRole.INSTRUCTOR,
            is_active=True,
        )
        subject = Subject(
            name="Source Physics",
            slug="source-physics",
            description="Source test subject",
            order=1,
        )
        db.add_all([student, instructor, subject])
        db.flush()
        topic = Topic(
            subject_id=subject.id,
            name="Source Motion",
            slug="source-motion",
            description="Source test topic",
        )
        db.add(topic)
        db.flush()

        published = ingest_source_file(
            db,
            first_pdf,
            first_pdf.name,
            instructor.id,
            subject_id=subject.id,
            title="Published Physics Source",
            description="Visible learning source",
            publish=True,
            topics=[topic.id],
        )
        draft = ingest_source_file(
            db,
            second_pdf,
            second_pdf.name,
            instructor.id,
            subject_id=subject.id,
            title="Private Draft Source",
            publish=False,
            topics=[topic.id],
        )
        db.commit()
        state = {
            "student_id": student.id,
            "instructor_id": instructor.id,
            "subject_id": subject.id,
            "topic_id": topic.id,
            "published_id": published.document.public_id,
            "published_sha": published.blob.sha256,
            "published_version_id": published.version.id,
            "draft_id": draft.document.public_id,
        }

    auth_state = {"user_id": state["student_id"]}

    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_current_user():
        with SessionLocal() as db:
            return db.get(User, auth_state["user_id"])

    app = FastAPI()
    app.include_router(sources.router, prefix="/api/sources")
    app.include_router(source_management.router, prefix="/api/source-management")
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user
    client = TestClient(app)

    yield {
        **state,
        "app": app,
        "client": client,
        "auth_state": auth_state,
        "SessionLocal": SessionLocal,
    }

    client.close()
    app.dependency_overrides.clear()
    get_source_storage.cache_clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_source_library_requires_authentication(source_app) -> None:
    app = FastAPI()
    app.include_router(sources.router, prefix="/api/sources")
    app.dependency_overrides[get_db] = source_app["app"].dependency_overrides[get_db]
    with TestClient(app) as unauthenticated_client:
        assert unauthenticated_client.get("/api/sources").status_code == 401


def test_library_lists_only_published_sources_and_filters(source_app) -> None:
    client = source_app["client"]
    response = client.get("/api/sources")
    assert response.status_code == 200
    body = response.json()
    assert body["total_documents"] == 1
    assert body["total_categories"] == 1
    assert body["categories"][0]["name"] == "Source Physics"
    assert body["categories"][0]["file_count"] == 1
    assert body["categories"][0]["files"][0]["title"] == "Published Physics Source"
    assert body["categories"][0]["files"][0]["status"] == SourceStatus.PUBLISHED.value
    assert "Private Draft Source" not in response.text

    assert client.get("/api/sources", params={"q": "Physics"}).json()["total_files"] == 1
    assert client.get("/api/sources", params={"q": "missing"}).json()["total_files"] == 0
    assert (
        client.get(
            "/api/sources",
            params={"subject_id": source_app["subject_id"], "topic_id": source_app["topic_id"]},
        ).json()["total_files"]
        == 1
    )
    assert client.get("/api/sources", params={"file_type": "docx"}).json()["total_files"] == 0


def test_source_metadata_and_content_are_stable_and_private(source_app) -> None:
    client = source_app["client"]
    source_id = source_app["published_id"]

    metadata = client.get(f"/api/sources/{source_id}")
    assert metadata.status_code == 200
    payload = metadata.json()
    assert payload["id"] == source_id
    assert payload["name"] == "published.pdf"
    assert payload["subject"]["slug"] == "source-physics"
    assert payload["topics"][0]["slug"] == "source-motion"
    assert payload["version"]["id"] == source_app["published_version_id"]
    assert not {"storage_key", "sha256", "path", "rights_status", "attribution"}.intersection(payload)

    legacy_id = client.get(f"/api/sources/{source_app['published_sha']}")
    assert legacy_id.status_code == 200
    assert legacy_id.json()["id"] == source_id

    content = client.get(f"/api/sources/{source_id}/content")
    assert content.status_code == 200
    assert content.content == PDF_ONE
    assert content.headers["content-type"] == "application/pdf"
    assert content.headers["x-content-type-options"] == "nosniff"
    assert "inline" in content.headers["content-disposition"]
    assert "attachment" not in content.headers["content-disposition"]


@pytest.mark.parametrize(
    "source_id",
    ["not-a-source", "0" * 64, "%2E%2E%5Csecret.pdf", "document.pdf%3Astream"],
)
def test_unknown_or_path_like_source_ids_are_not_accessible(source_app, source_id: str) -> None:
    client = source_app["client"]
    assert client.get(f"/api/sources/{source_id}").status_code == 404
    assert client.get(f"/api/sources/{source_id}/content").status_code == 404


def test_bookmark_progress_history_and_reporting(source_app) -> None:
    client = source_app["client"]
    source_id = source_app["published_id"]

    bookmark = client.put(
        f"/api/sources/{source_id}/bookmark",
        json={"page": 2, "note": "Review this derivation"},
    )
    assert bookmark.status_code == 200
    assert bookmark.json() == {
        "bookmarked": True,
        "page": 2,
        "note": "Review this derivation",
    }
    bookmarks = client.get("/api/sources/me/bookmarks").json()
    assert bookmarks["total_files"] == 1
    assert bookmarks["categories"][0]["files"][0]["is_bookmarked"] is True

    progress = client.put(
        f"/api/sources/{source_id}/progress",
        json={"page": 3, "progress_percent": 42.5, "session_id": "reader-session-1"},
    )
    assert progress.status_code == 200
    assert progress.json()["last_page"] == 3
    assert progress.json()["progress_percent"] == 42.5
    history = client.get("/api/sources/me/history").json()
    assert history["total_files"] == 1
    assert history["categories"][0]["files"][0]["reading_progress"] == 42.5

    report = client.post(
        f"/api/sources/{source_id}/reports",
        json={
            "category": "incorrect_content",
            "message": "The equation on this page needs review.",
            "version_id": source_app["published_version_id"],
        },
    )
    assert report.status_code == 201
    assert report.json()["status"] == "open"

    with source_app["SessionLocal"]() as db:
        assert db.query(SourceReadEvent).filter_by(user_id=source_app["student_id"]).count() == 1
        stored_report = db.query(SourceReport).one()
        stored_document = db.query(SourceDocument).filter_by(public_id=source_id).one()
        assert stored_report.document_id == stored_document.id
        assert stored_report.message == "The equation on this page needs review."

    assert client.delete(f"/api/sources/{source_id}/bookmark").json() == {
        "bookmarked": False
    }
    assert client.get("/api/sources/me/bookmarks").json()["total_files"] == 0


def test_staff_rbac_upload_lifecycle_report_resolution_and_dedup(source_app) -> None:
    client = source_app["client"]
    assert client.get("/api/source-management").status_code == 403

    source_app["auth_state"]["user_id"] = source_app["instructor_id"]
    taxonomy = client.get("/api/source-management/taxonomy")
    assert taxonomy.status_code == 200
    assert taxonomy.json()["subjects"][0]["slug"] == "source-physics"

    form = {
        "title": "Uploaded Staff Source",
        "description": "Must pass review before students can see it.",
        "subject_id": str(source_app["subject_id"]),
        "topic_ids": str(source_app["topic_id"]),
        "kind": "assessment",
        "rights_status": "internal_learning",
        "attribution": "Instructor upload",
    }
    first_upload = client.post(
        "/api/source-management/upload",
        data=form,
        files={"file": ("staff-source.pdf", PDF_UPLOAD, "application/pdf")},
    )
    assert first_upload.status_code == 201, first_upload.text
    upload_body = first_upload.json()
    managed_id = upload_body["document"]["id"]
    assert upload_body["deduplicated"] is False
    assert upload_body["document"]["status"] == SourceStatus.INBOX.value
    assert upload_body["document"]["rights_status"] == "internal_learning"
    assert upload_body["document"]["attribution"] == "Instructor upload"

    review = client.post(
        f"/api/source-management/{managed_id}/review", json={"notes": "Ready for review"}
    )
    assert review.status_code == 200
    assert review.json()["status"] == SourceStatus.REVIEW_PENDING.value
    publish = client.post(
        f"/api/source-management/{managed_id}/publish", json={"notes": "Approved"}
    )
    assert publish.status_code == 200
    assert publish.json()["status"] == SourceStatus.PUBLISHED.value

    duplicate_form = {**form, "title": "Second Logical Source"}
    duplicate = client.post(
        "/api/source-management/upload",
        data=duplicate_form,
        files={"file": ("same-content.pdf", PDF_UPLOAD, "application/pdf")},
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["deduplicated"] is True
    with source_app["SessionLocal"]() as db:
        # Initial published/draft files plus one content-addressed upload blob.
        assert db.query(SourceBlob).count() == 3

    source_app["auth_state"]["user_id"] = source_app["student_id"]
    library = client.get("/api/sources").json()
    assert library["total_files"] == 2
    report = client.post(
        f"/api/sources/{managed_id}/reports",
        json={"category": "formatting", "message": "A diagram is difficult to read."},
    )
    assert report.status_code == 201

    source_app["auth_state"]["user_id"] = source_app["instructor_id"]
    reports = client.get(f"/api/source-management/{managed_id}/reports")
    assert reports.status_code == 200
    report_id = reports.json()[0]["id"]
    resolved = client.post(
        f"/api/source-management/{managed_id}/reports/{report_id}/resolve",
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"


def _published_cited_question(source_app) -> int:
    with source_app["SessionLocal"]() as db:
        bank = QuestionBank(
            topic_id=source_app["topic_id"],
            name="Published source transition bank",
        )
        db.add(bank)
        db.flush()
        question = Question(
            question_bank_id=bank.id,
            title="Published question tied to source",
            question_type=QuestionType.NUMERICAL,
            difficulty=QuestionDifficulty.EASY,
            content_html="<p>What is 1 + 1?</p>",
            expected_answer="2",
            workflow_status=QuestionWorkflowStatus.PUBLISHED.value,
            is_published=True,
            requires_citation=True,
            published_at=datetime.utcnow(),
            author_id=source_app["instructor_id"],
        )
        db.add(question)
        db.flush()
        db.add(
            QuestionSourceCitation(
                question_id=question.id,
                source_version_id=source_app["published_version_id"],
                page_start=1,
                purpose="prompt",
                created_by_id=source_app["instructor_id"],
            )
        )
        db.commit()
        return question.id


@pytest.mark.parametrize(
    ("transition", "expected_source_status"),
    [
        ("metadata", SourceStatus.INBOX.value),
        ("version", SourceStatus.INBOX.value),
        ("archive", SourceStatus.ARCHIVED.value),
    ],
)
def test_every_transition_away_from_published_demotes_cited_questions(
    source_app, transition: str, expected_source_status: str
) -> None:
    client = source_app["client"]
    source_id = source_app["published_id"]
    question_id = _published_cited_question(source_app)
    source_app["auth_state"]["user_id"] = source_app["instructor_id"]

    if transition == "metadata":
        response = client.patch(
            f"/api/source-management/{source_id}",
            json={"description": "Reclassified metadata requires another review."},
        )
    elif transition == "version":
        response = client.post(
            f"/api/source-management/{source_id}/version",
            data={"notes": "Replacement version"},
            files={"file": ("replacement.pdf", PDF_NEW_VERSION, "application/pdf")},
        )
    else:
        response = client.post(
            f"/api/source-management/{source_id}/archive",
            json={"notes": "Temporarily withdrawn"},
        )

    assert response.status_code in {200, 201}, response.text
    payload = response.json()
    source_payload = payload["document"] if transition == "version" else payload
    assert source_payload["status"] == expected_source_status

    with source_app["SessionLocal"]() as db:
        question = db.get(Question, question_id)
        assert question.workflow_status == QuestionWorkflowStatus.APPROVED.value
        assert question.is_published is False
        assert question.published_at is None
