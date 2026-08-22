"""Integration coverage for reviewed, source-grounded learner questions."""

import asyncio
import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ.setdefault("APP_ENV", "testing")

from app.core.database import Base, get_db
from app.core.permissions import UserRole
from app.core.security import create_access_token, hash_password
from app.api import auth, journey, learning, question_management
from app.models.models import (
    Question,
    QuestionBank,
    QuestionDifficulty,
    QuestionType,
    QuestionWorkflowStatus,
    SourceBlob,
    SourceDocument,
    SourceDocumentTopic,
    SourceStatus,
    SourceVersion,
    Subject,
    Topic,
    User,
)
from app.services import question_generation


app = FastAPI()
app.include_router(auth.router, prefix="/api/auth")
app.include_router(journey.router, prefix="/api/journey")
app.include_router(learning.router, prefix="/api/learning")
app.include_router(question_management.router, prefix="/api/question-management")


@pytest.fixture()
def db_session():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    session = Session(bind=test_engine, expire_on_commit=False)

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(test_engine)
        test_engine.dispose()


@pytest.fixture()
def client(db_session):
    with TestClient(app) as test_client:
        yield test_client


def _headers_for(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _staff(db: Session) -> tuple[User, dict[str, str]]:
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"reviewer-{suffix}@example.com",
        username=f"reviewer-{suffix}",
        full_name="Question Reviewer",
        hashed_password=hash_password("Reviewer123!"),
        role=UserRole.INSTRUCTOR,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user, _headers_for(user)


def _student_headers(client: TestClient) -> dict[str, str]:
    suffix = uuid.uuid4().hex[:10]
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"learner-{suffix}@example.com",
            "username": f"learner-{suffix}",
            "password": "Learner123!",
            "full_name": "Workflow Learner",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _catalog(
    db: Session,
    staff: User,
    *,
    source_status: str = SourceStatus.PUBLISHED.value,
) -> tuple[Subject, Topic, QuestionBank, SourceDocument, SourceVersion]:
    suffix = uuid.uuid4().hex
    subject = Subject(
        name=f"Workflow Subject {suffix[:8]}",
        slug=f"workflow-subject-{suffix}",
        order=25,
    )
    db.add(subject)
    db.flush()
    topic = Topic(
        subject_id=subject.id,
        name="Grounded calculations",
        slug=f"grounded-{suffix}",
    )
    db.add(topic)
    db.flush()
    bank = QuestionBank(topic_id=topic.id, name="Workflow Test Bank")
    document = SourceDocument(
        subject_id=subject.id,
        title="Verified Engineering Notes",
        status=source_status,
        created_by_id=staff.id,
    )
    digest = uuid.uuid4().hex + uuid.uuid4().hex
    blob = SourceBlob(
        sha256=digest,
        size_bytes=100,
        media_type="application/pdf",
        extension=".pdf",
        storage_backend="local",
        storage_key=f"blobs/{digest[:2]}/{digest}.pdf",
    )
    db.add_all([bank, document, blob])
    db.flush()
    version = SourceVersion(
        document_id=document.id,
        blob_id=blob.id,
        version_number=1,
        original_filename="verified-notes.pdf",
        page_count=12,
        uploaded_by_id=staff.id,
    )
    db.add_all(
        [version, SourceDocumentTopic(document_id=document.id, topic_id=topic.id, is_primary=True)]
    )
    db.commit()
    return subject, topic, bank, document, version


def _draft_body(topic_id: int, title: str = "Source-grounded current") -> dict:
    return {
        "topic_id": topic_id,
        "title": title,
        "question_type": "numerical",
        "difficulty": "easy",
        "content_html": "<p>A 12 V source is connected to 6 ohm. Find current.</p>",
        "solution_html": "<p>I = 12 / 6 = 2 A.</p>",
        "explanation": "Apply Ohm's law.",
        "expected_answer": "2 A",
        "numerical_tolerance": 0.001,
        "accepted_units": ["A", "mA"],
        "xp_reward": 10,
    }


def test_only_fully_published_questions_reach_learners(client: TestClient, db_session: Session):
    staff, _ = _staff(db_session)
    _, topic, bank, _, _ = _catalog(db_session, staff)
    visible = Question(
        question_bank_id=bank.id,
        title="Visible",
        question_type=QuestionType.NUMERICAL,
        difficulty=QuestionDifficulty.EASY,
        content_html="<p>1 + 1?</p>",
        expected_answer="2",
        workflow_status=QuestionWorkflowStatus.PUBLISHED.value,
        is_published=True,
        requires_citation=False,
    )
    inconsistent = Question(
        question_bank_id=bank.id,
        title="Approved but boolean true",
        question_type=QuestionType.NUMERICAL,
        difficulty=QuestionDifficulty.EASY,
        content_html="<p>Hidden</p>",
        expected_answer="2",
        workflow_status=QuestionWorkflowStatus.APPROVED.value,
        is_published=True,
        requires_citation=False,
    )
    draft = Question(
        question_bank_id=bank.id,
        title="Draft",
        question_type=QuestionType.NUMERICAL,
        difficulty=QuestionDifficulty.EASY,
        content_html="<p>Hidden</p>",
        expected_answer="2",
        workflow_status=QuestionWorkflowStatus.DRAFT.value,
        is_published=False,
        requires_citation=True,
    )
    db_session.add_all([visible, inconsistent, draft])
    db_session.commit()
    learner = _student_headers(client)

    next_problem = client.get(f"/api/journey/next?topic_id={topic.id}", headers=learner)
    assert next_problem.status_code == 200
    assert next_problem.json()["question"]["id"] == visible.id
    listed_ids = {item["id"] for item in client.get("/api/learning/problems/", headers=learner).json()}
    assert visible.id in listed_ids
    assert inconsistent.id not in listed_ids
    assert draft.id not in listed_ids
    assert client.post(
        f"/api/learning/problems/{inconsistent.id}/submit",
        headers=learner,
        json={"session_id": uuid.uuid4().hex, "answer": "2"},
    ).status_code == 404


def test_staff_can_review_publish_and_recommend_exact_source(
    client: TestClient, db_session: Session
):
    staff, staff_headers = _staff(db_session)
    _, topic, _, document, version = _catalog(db_session, staff)
    learner = _student_headers(client)

    created = client.post(
        "/api/question-management",
        headers=staff_headers,
        json=_draft_body(topic.id),
    )
    assert created.status_code == 201, created.text
    question_id = created.json()["id"]
    assert created.json()["workflow_status"] == "draft"
    assert created.json()["is_published"] is False

    citation = client.post(
        f"/api/question-management/{question_id}/citations",
        headers=staff_headers,
        json={
            "source_version_id": version.id,
            "page_start": 2,
            "page_end": 3,
            "section_label": "Ohm's law",
            "purpose": "prompt",
            "excerpt": "The source excerpt is staff-only.",
        },
    )
    assert citation.status_code == 201, citation.text
    assert citation.json()["href"] == (
        f"/sources/{document.public_id}?version_id={version.id}&version=1&page=2"
    )

    submitted = client.post(
        f"/api/question-management/{question_id}/submit-review", headers=staff_headers
    )
    assert submitted.status_code == 200, submitted.text
    approved = client.post(
        f"/api/question-management/{question_id}/review",
        headers=staff_headers,
        json={"action": "approve", "notes": "Calculation and citation verified."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["workflow_status"] == "approved"
    published = client.post(
        f"/api/question-management/{question_id}/publish", headers=staff_headers
    )
    assert published.status_code == 200, published.text
    assert published.json()["workflow_status"] == "published"
    assert published.json()["is_published"] is True

    journey = client.get(f"/api/journey/next?topic_id={topic.id}", headers=learner)
    assert journey.status_code == 200
    sources = journey.json()["question"]["sources"]
    assert sources[0]["public_id"] == document.public_id
    assert sources[0]["page_start"] == 2
    assert "excerpt" not in sources[0]

    graded = client.post(
        f"/api/learning/problems/{question_id}/submit",
        headers=learner,
        json={"session_id": uuid.uuid4().hex, "answer": "2 A"},
    )
    assert graded.status_code == 200, graded.text
    recommendation = graded.json()["recommended_sources"][0]
    assert recommendation["href"] == (
        f"/sources/{document.public_id}?version_id={version.id}&version=1&page=2"
    )
    assert "excerpt" not in recommendation


def test_publish_revalidates_source_and_legacy_question_can_remain_citationless(
    client: TestClient, db_session: Session
):
    staff, staff_headers = _staff(db_session)
    _, topic, bank, document, version = _catalog(db_session, staff)
    created = client.post(
        "/api/question-management", headers=staff_headers, json=_draft_body(topic.id)
    ).json()
    question_id = created["id"]
    assert client.post(
        f"/api/question-management/{question_id}/citations",
        headers=staff_headers,
        json={"source_version_id": version.id, "page_start": 1, "purpose": "prompt"},
    ).status_code == 201
    assert client.post(
        f"/api/question-management/{question_id}/submit-review", headers=staff_headers
    ).status_code == 200
    assert client.post(
        f"/api/question-management/{question_id}/review",
        headers=staff_headers,
        json={"action": "approve"},
    ).status_code == 200
    document.status = SourceStatus.ARCHIVED.value
    db_session.commit()
    blocked = client.post(
        f"/api/question-management/{question_id}/publish", headers=staff_headers
    )
    assert blocked.status_code == 422

    legacy = Question(
        question_bank_id=bank.id,
        title="Grandfathered question",
        question_type=QuestionType.NUMERICAL,
        difficulty=QuestionDifficulty.EASY,
        content_html="<p>2 + 2?</p>",
        expected_answer="4",
        workflow_status=QuestionWorkflowStatus.APPROVED.value,
        is_published=False,
        requires_citation=False,
        author_id=staff.id,
    )
    db_session.add(legacy)
    db_session.commit()
    response = client.post(
        f"/api/question-management/{legacy.id}/publish", headers=staff_headers
    )
    assert response.status_code == 200, response.text


def test_rbac_subject_validation_and_disabled_ai(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    staff, staff_headers = _staff(db_session)
    _, topic, _, _, version = _catalog(db_session, staff)
    learner = _student_headers(client)
    assert client.get("/api/question-management", headers=learner).status_code == 403

    question_id = client.post(
        "/api/question-management", headers=staff_headers, json=_draft_body(topic.id)
    ).json()["id"]
    other_subject, other_topic, _, _, other_version = _catalog(db_session, staff)
    assert other_subject.id != topic.subject_id
    assert other_topic.subject_id == other_subject.id
    mismatch = client.post(
        f"/api/question-management/{question_id}/citations",
        headers=staff_headers,
        json={"source_version_id": other_version.id, "page_start": 1, "purpose": "prompt"},
    )
    assert mismatch.status_code == 422

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    disabled = client.post(
        "/api/question-management/generate",
        headers=staff_headers,
        json={
            "topic_id": topic.id,
            "source_version_id": version.id,
            "count": 1,
            "page_start": 1,
        },
    )
    assert disabled.status_code == 503
    assert "disabled" in disabled.json()["detail"].lower()


def test_openai_generation_uses_strict_non_stored_structured_output(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict = {}
    generated = {
        "questions": [
            {
                "title": "Ohm's law draft",
                "question_type": "numerical",
                "difficulty": "easy",
                "prompt": "Find the current for 12 V across 6 ohm.",
                "solution": "I = V/R = 2 A.",
                "explanation": "Current is voltage divided by resistance.",
                "expected_answer": "2 A",
                "numerical_tolerance": 0.001,
                "accepted_units": ["A"],
                "bloom_level": "apply",
                "estimated_time_minutes": 3,
                "xp_reward": 10,
            }
        ]
    }

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "id": "resp_test",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": __import__("json").dumps(generated)}
                        ],
                    }
                ],
            }

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_options"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["request"] = kwargs
            return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setattr(question_generation.httpx, "AsyncClient", FakeClient)
    drafts, metadata = asyncio.run(
        question_generation.generate_questions_from_text(
            source_text="Ohm's law states that current equals voltage divided by resistance. " * 3,
            subject_name="Circuit Analysis",
            topic_name="Ohm's law",
            count=1,
        )
    )

    request = captured["request"]["json"]
    assert request["store"] is False
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["strict"] is True
    assert request["text"]["format"]["schema"]["additionalProperties"] is False
    assert captured["request"]["headers"]["Authorization"] == "Bearer test-key"
    assert drafts[0].content_html == "<p>Find the current for 12 V across 6 ohm.</p>"
    assert metadata == {
        "provider": "openai",
        "model": "test-model",
        "response_id": "resp_test",
        "store": False,
    }
