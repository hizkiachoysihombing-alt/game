"""PostgreSQL integration tests for the current student milestone."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ.setdefault("APP_ENV", "testing")

from app.core.database import engine, get_db
from app.main import app
from app.models.models import (
    Course, GamificationProfile, Lesson, Module, Question, QuestionBank, ReasoningDiagnosis,
    QuestionDifficulty, QuestionType, Subject, Topic, User,
)
from app.core.security import hash_password
from app.core.permissions import UserRole
from app.services.assessment import grade_question


if engine.dialect.name != "postgresql":
    raise RuntimeError("Integration tests require PostgreSQL; SQLite is not supported.")


@pytest.fixture()
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    def override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(client: TestClient) -> dict[str, str]:
    suffix = uuid.uuid4().hex[:8]
    response = client.post("/api/auth/register", json={"email": f"student-{suffix}@example.com", "username": f"student-{suffix}", "password": "Student123!", "full_name": "Test Student"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_course(db: Session) -> tuple[Course, Lesson, Question]:
    suffix = uuid.uuid4().hex[:8]
    instructor = User(email=f"instructor-{suffix}@example.com", username=f"instructor-{suffix}", full_name="Instructor", hashed_password=hash_password("Instructor123!"), role=UserRole.INSTRUCTOR)
    subject = Subject(name=f"Circuit Test {suffix}", slug=f"circuit-{suffix}")
    db.add_all([instructor, subject]); db.flush()
    course = Course(subject_id=subject.id, instructor_id=instructor.id, name="Circuit Integration", slug=f"course-{suffix}", is_published=True)
    db.add(course); db.flush()
    module = Module(course_id=course.id, name="Ohm's Law", order=1)
    topic = Topic(subject_id=subject.id, name="Ohm's Law", slug=f"ohm-{suffix}")
    db.add_all([module, topic]); db.flush()
    lesson = Lesson(module_id=module.id, name="Voltage and current", content_html="<p>Ohm's law</p>", order=1, is_published=True)
    db.add(lesson); db.flush()
    bank = QuestionBank(topic_id=topic.id, name="Test Bank")
    db.add(bank); db.flush()
    question = Question(question_bank_id=bank.id, title="Current", question_type=QuestionType.NUMERICAL, difficulty=QuestionDifficulty.EASY, content_html="12 V / 6 ohm", expected_answer="2 A", accepted_units=["A", "mA"], numerical_tolerance=0.001, xp_reward=10, is_published=True)
    db.add(question); db.commit()
    return course, lesson, question


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200


def test_student_flow_persists_in_postgres(client: TestClient, db_session: Session):
    _, _, question = seed_course(db_session)
    headers = auth_headers(client)
    result = client.post(f"/api/learning/problems/{question.id}/submit", headers=headers, json={"session_id": uuid.uuid4().hex, "answer": {"value": 2000, "unit": "mA"}, "response_time_seconds": 12})
    assert result.status_code == 200, result.text
    assert result.json()["is_correct"] is True
    assert result.json()["mastery"] > 0
    assert result.json()["ranked_points"] > 0
    dashboard = client.get("/api/dashboard/student", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    payload = dashboard.json()
    assert payload["gamification"]["total_xp"] >= 10
    assert payload["gamification"]["current_streak_days"] == 1
    assert payload["subscription"]["energy_remaining"] == 24
    assert "courses" not in payload
    journey = client.get("/api/journey/map", headers=headers)
    assert journey.status_code == 200
    assert len(journey.json()["subjects"]) >= 30
    first_section = journey.json()["subjects"][0]["topics"][0]
    assert [unit["name"] for unit in first_section["units"]] == ["Warm-up", "Foundation", "Applied practice", "Challenge", "Endless Circuit"]
    assert client.get("/api/journey/next", headers=headers).status_code == 200
    topic_response = client.get(f"/api/journey/next?topic_id={question.question_bank.topic_id}", headers=headers)
    assert topic_response.status_code == 200
    assert topic_response.json()["question"]["id"] == question.id
    unit_response = client.get(f"/api/journey/next?topic_id={question.question_bank.topic_id}&unit=1", headers=headers)
    assert unit_response.status_code == 200
    assert unit_response.json()["unit"] == 1
    leaderboard = client.get("/api/gamification/leaderboard", headers=headers)
    assert leaderboard.status_code == 200
    assert any(row["user_id"] == payload["student"]["id"] for row in leaderboard.json())
    for period in ("daily", "monthly"):
        period_board = client.get(f"/api/gamification/leaderboard?period={period}&category=ranked_engineering", headers=headers)
        assert period_board.status_code == 200
        assert any(row["user_id"] == payload["student"]["id"] for row in period_board.json())


def test_submission_is_idempotent(client: TestClient, db_session: Session):
    _, _, question = seed_course(db_session)
    headers = auth_headers(client)
    session_id = uuid.uuid4().hex
    body = {"session_id": session_id, "answer": "2 A"}
    first = client.post(f"/api/learning/problems/{question.id}/submit", headers=headers, json=body)
    second = client.post(f"/api/learning/problems/{question.id}/submit", headers=headers, json=body)
    assert first.status_code == second.status_code == 200
    assert second.json()["duplicate"] is True
    user_id = client.get("/api/users/me", headers=headers).json()["id"]
    assert db_session.query(GamificationProfile).filter_by(user_id=user_id).one().problems_solved == 1


def test_wrong_answer_creates_diagnosis_and_rbac_is_enforced(client: TestClient, db_session: Session):
    _, _, question = seed_course(db_session)
    headers = auth_headers(client)
    response = client.post(f"/api/learning/problems/{question.id}/submit", headers=headers, json={"session_id": uuid.uuid4().hex, "answer": "5 A"})
    assert response.status_code == 200
    assert response.json()["is_correct"] is False
    assert response.json()["diagnosis"] == "ARITHMETIC_ERROR"
    user_id = client.get("/api/users/me", headers=headers).json()["id"]
    assert db_session.query(ReasoningDiagnosis).filter_by(user_id=user_id, error_detected=True).count() == 1
    assert client.get("/api/admin/users", headers=headers).status_code == 403


def test_coding_question_uses_safe_declarative_checks():
    question = Question(
        coding_language="python",
        question_type=QuestionType.SHORT_ANSWER,
        test_cases=[
            {"name": "Defines function", "required": ["def calculate"], "forbidden": ["eval("]},
            {"name": "Returns value", "required": ["return"], "forbidden": ["exec("]},
        ],
    )
    passed = grade_question(question, {"code": "def calculate(value):\n    return value * 2"})
    unsafe = grade_question(question, {"code": "def calculate(value):\n    return eval(value)"})
    assert passed.is_correct is True
    assert passed.score == 100
    assert unsafe.is_correct is False
    assert unsafe.error_code == "CODE_TEST_FAILED"


def test_user_can_update_profile_identity(client: TestClient):
    headers = auth_headers(client)
    suffix = uuid.uuid4().hex[:8]
    response = client.put("/api/users/me", headers=headers, json={
        "full_name": "Updated Learner",
        "username": f"updated-{suffix}",
        "email": f"updated-{suffix}@example.com",
        "bio": "Building embedded and control projects.",
        "major": "Embedded systems",
    })
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Learner"
    assert response.json()["username"] == f"updated-{suffix}"
    assert client.get("/api/users/me", headers=headers).json()["major"] == "Embedded systems"
