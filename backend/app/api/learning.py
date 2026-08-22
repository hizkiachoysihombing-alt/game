"""
Learning and assessment API routes (lessons, quizzes, problems).
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.core.cache import cache_delete
from app.models.models import (
    Lesson, LessonProgress, Module, Course, Question, ProblemSubmission,
    ProblemSubmissionStatus, GamificationProfile, XPTransaction, UsageQuota,
    UsageLedger, Subscription, SubscriptionPlan,
)
from app.services.assessment import grade_question
from app.services.question_workflow import (
    is_learner_visible,
    learner_question_filters,
    learner_source_recommendations,
)
from app.services.progress import (
    evaluate_achievements, get_profile, grant_xp, record_activity,
    record_diagnosis, update_mastery, update_quests, update_ranked_score,
)

router = APIRouter()


class ProblemSubmissionRequest(BaseModel):
    session_id: str
    answer: dict | str | float | int | None = None
    working_notes: str | None = None
    response_time_seconds: float | None = Field(default=None, ge=0, le=3600)


def reset_quota_if_needed(quota: UsageQuota) -> None:
    now = datetime.utcnow()
    if quota.daily_reset_at is None or quota.daily_reset_at <= now:
        quota.daily_problems_used = 0
        quota.daily_reset_at = now + timedelta(days=1)
        quota.last_reset_at = now


def consume_energy(db: Session, user_id: int, submission_id: int | None, key: str) -> None:
    quota = db.query(UsageQuota).filter(UsageQuota.user_id == user_id).with_for_update().first()
    if quota is None:
        quota = UsageQuota(user_id=user_id, daily_problems_limit=settings.FREE_PLAN_DAILY_ENERGY)
        db.add(quota)
        db.flush()
    elif quota.daily_problems_limit < settings.FREE_PLAN_DAILY_ENERGY:
        quota.daily_problems_limit = settings.FREE_PLAN_DAILY_ENERGY
    reset_quota_if_needed(quota)
    subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    unlimited = subscription is not None and subscription.plan != SubscriptionPlan.FREE
    if not unlimited and quota.daily_problems_used >= quota.daily_problems_limit:
        raise HTTPException(status_code=429, detail="Daily Learning Energy exhausted")
    existing = db.query(UsageLedger).filter(UsageLedger.idempotency_key == key).first()
    if existing:
        return
    if not unlimited:
        quota.daily_problems_used += 1
    db.add(UsageLedger(user_id=user_id, feature_key="problem_solving", usage_type="consumed", quantity=1, problem_submission_id=submission_id, idempotency_key=key))


@router.get("/lessons/{lesson_id}")
async def get_lesson(lesson_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get lesson content."""
    lesson = db.query(Lesson).join(Module).join(Course).filter(Lesson.id == lesson_id, Lesson.is_published.is_(True), Course.is_published.is_(True)).first()
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    progress = db.query(LessonProgress).filter(LessonProgress.user_id == current_user.id, LessonProgress.lesson_id == lesson_id).first()
    if progress is None:
        progress = LessonProgress(user_id=current_user.id, lesson_id=lesson_id, last_viewed_at=datetime.utcnow())
        db.add(progress)
    else:
        progress.last_viewed_at = datetime.utcnow()
    db.commit()
    return {"id": lesson.id, "name": lesson.name, "content_html": lesson.content_html, "module_id": lesson.module_id, "progress": {"is_completed": progress.is_completed}}


@router.post("/lessons/{lesson_id}/mark-complete")
async def mark_lesson_complete(
    lesson_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark lesson as completed."""
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    progress = db.query(LessonProgress).filter(LessonProgress.user_id == current_user.id, LessonProgress.lesson_id == lesson_id).first()
    if progress is None:
        progress = LessonProgress(user_id=current_user.id, lesson_id=lesson_id)
        db.add(progress)
    if not progress.is_completed:
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()
    db.commit()
    return {"lesson_id": lesson_id, "is_completed": True}


@router.get("/problems/")
async def list_problems(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get available problems."""
    questions = db.query(Question).filter(*learner_question_filters()).order_by(Question.id).limit(20).all()
    return [{"id": item.id, "title": item.title, "content_html": item.content_html, "question_type": item.question_type.value, "difficulty": item.difficulty.value, "answers": [{"id": answer.id, "text": answer.text, "order": answer.order} for answer in item.answers], "sources": learner_source_recommendations(item, purposes={"prompt"})} for item in questions]


@router.post("/problems/{problem_id}/submit")
async def submit_problem(
    problem_id: int,
    submission_data: ProblemSubmissionRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a problem solution."""
    question = db.query(Question).filter(Question.id == problem_id, *learner_question_filters()).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Problem not found")
    submission = db.query(ProblemSubmission).filter(ProblemSubmission.session_id == submission_data.session_id).first()
    if submission is not None:
        return {"id": submission.id, "is_correct": submission.is_correct, "score": submission.score, "xp_awarded": submission.xp_awarded, "feedback": submission.feedback, "duplicate": True, "recommended_sources": learner_source_recommendations(question)}
    stored_answer = submission_data.answer
    if submission_data.response_time_seconds is not None:
        stored_answer = dict(stored_answer) if isinstance(stored_answer, dict) else {"value": stored_answer}
        stored_answer["response_time_seconds"] = submission_data.response_time_seconds
    submission = ProblemSubmission(user_id=current_user.id, question_id=problem_id, session_id=submission_data.session_id, answer=stored_answer, working_notes=submission_data.working_notes, status=ProblemSubmissionStatus.SUBMITTED, submitted_at=datetime.utcnow())
    db.add(submission)
    db.flush()
    consume_energy(db, current_user.id, submission.id, f"problem:{submission_data.session_id}")
    grade = grade_question(question, submission_data.answer)
    is_correct = grade.is_correct
    xp = question.xp_reward or (settings.BASE_XP_EASY if question.difficulty.value in ("introductory", "easy") else settings.BASE_XP_MEDIUM)
    if not is_correct:
        xp = 0
    profile = get_profile(db, current_user.id)
    record_activity(profile, is_correct)
    grant_xp(db, profile, xp, "problem_solved", problem_id)
    mastery = update_mastery(db, current_user.id, question, is_correct)
    submission.is_correct = is_correct
    submission.score = grade.score
    submission.xp_awarded = xp
    submission.status = ProblemSubmissionStatus.GRADED
    submission.feedback = question.explanation if is_correct and question.explanation else grade.feedback
    submission.graded_at = datetime.utcnow()
    record_diagnosis(db, current_user.id, submission.id, grade.error_code, grade.feedback, question.question_bank.topic.name)
    update_quests(db, current_user.id)
    evaluate_achievements(db, current_user.id)
    ranked_points = update_ranked_score(db, current_user.id, question, is_correct, submission_data.response_time_seconds)
    question.times_answered = (question.times_answered or 0) + 1
    previous_accuracy = question.average_accuracy or 0.0
    question.average_accuracy = ((previous_accuracy * (question.times_answered - 1)) + (100.0 if is_correct else 0.0)) / question.times_answered
    db.commit()
    if ranked_points:
        await cache_delete("leaderboard:weekly:ranked_engineering")
        await cache_delete("leaderboard:daily:ranked_engineering")
        await cache_delete("leaderboard:monthly:ranked_engineering")
    return {"id": submission.id, "is_correct": is_correct, "score": submission.score, "xp_awarded": xp, "ranked_points": ranked_points, "feedback": submission.feedback, "mastery": mastery.mastery_level, "diagnosis": grade.error_code, "recommended_sources": learner_source_recommendations(question)}


@router.get("/quizzes/{quiz_id}")
async def get_quiz(quiz_id: int, db: Session = Depends(get_db)):
    """Get quiz details."""
    from app.models.models import Quiz
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.is_published.is_(True)).first()
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    visible_questions = [question for question in quiz.questions if is_learner_visible(question)]
    return {"id": quiz.id, "name": quiz.name, "description": quiz.description, "time_limit_minutes": quiz.time_limit_minutes, "questions": [{"id": question.id, "title": question.title, "content_html": question.content_html} for question in visible_questions]}


@router.post("/quizzes/{quiz_id}/submit")
async def submit_quiz(
    quiz_id: int,
    responses: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit quiz answers."""
    completed = db.query(LessonProgress).filter(LessonProgress.user_id == current_user.id, LessonProgress.is_completed.is_(True)).count()
    total = db.query(LessonProgress).filter(LessonProgress.user_id == current_user.id).count()
    return {"completed_lessons": completed, "tracked_lessons": total}


@router.get("/progress")
async def get_learning_progress(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get student's learning progress."""
    progress = db.query(LessonProgress).filter(LessonProgress.user_id == current_user.id).all()
    return [{"lesson_id": item.lesson_id, "is_completed": item.is_completed, "completed_at": item.completed_at, "last_viewed_at": item.last_viewed_at} for item in progress]


@router.get("/mastery")
async def get_mastery(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get mastery levels for all topics."""
    from app.models.models import MasteryRecord, Topic
    records = db.query(MasteryRecord, Topic).join(Topic, Topic.id == MasteryRecord.topic_id).filter(MasteryRecord.user_id == current_user.id).all()
    return [{"topic_id": topic.id, "topic_name": topic.name, "mastery_level": record.mastery_level, "confidence": record.confidence, "needs_review": record.needs_review} for record, topic in records]
