"""Adaptive, course-independent learning journey."""

import random
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import GamificationProfile, MasteryRecord, ProblemSubmission, Question, QuestionBank, Subject, Topic

router = APIRouter()

UNIT_STAGES = [
    (1, "Warm-up", 0, 0),
    (2, "Foundation", 1, 10),
    (3, "Applied practice", 3, 30),
    (4, "Challenge", 6, 55),
    (5, "Endless Circuit", 10, 75),
]


def unlocked_subject_count(profile: GamificationProfile | None) -> int:
    # One new chapter per level keeps prerequisites meaningful: a new learner
    # completes Basic Mathematics before Physics and Engineering Mathematics.
    return max(1, min(64, profile.level if profile else 1))


@router.get("/map")
async def journey_map(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(GamificationProfile).filter_by(user_id=current_user.id).first()
    unlocked_count = unlocked_subject_count(profile)
    mastery = {row.topic_id: row for row in db.query(MasteryRecord).filter_by(user_id=current_user.id).all()}
    subjects = db.query(Subject).options(selectinload(Subject.topics)).filter(Subject.order < 900).order_by(Subject.order, Subject.id).all()
    question_counts = dict(
        db.query(QuestionBank.topic_id, func.count(Question.id))
        .join(Question, Question.question_bank_id == QuestionBank.id)
        .filter(Question.is_published.is_(True))
        .group_by(QuestionBank.topic_id)
        .all()
    )
    payload = []
    for index, subject in enumerate(subjects):
        unlocked = index < unlocked_count
        topics = []
        for topic in subject.topics:
            record = mastery.get(topic.id)
            question_count = question_counts.get(topic.id, 0)
            attempts = record.times_practiced if record else 0
            mastery_level = record.mastery_level if record else 0
            units = []
            for unit_index, unit_name, required_attempts, required_mastery in UNIT_STAGES:
                unit_unlocked = unlocked and question_count > 0 and attempts >= required_attempts and mastery_level >= required_mastery
                if unit_index < 5:
                    next_attempts, next_mastery = UNIT_STAGES[unit_index][2], UNIT_STAGES[unit_index][3]
                    completed = attempts >= next_attempts and mastery_level >= next_mastery
                else:
                    completed = False
                units.append({"index": unit_index, "name": unit_name, "status": "endless" if unit_index == 5 and unit_unlocked else "completed" if completed else "current" if unit_unlocked else "locked", "required_attempts": required_attempts, "required_mastery": required_mastery})
            topics.append({"id": topic.id, "name": topic.name, "mastery": mastery_level, "attempts": attempts, "available_questions": question_count, "status": "mastered" if record and record.mastered else "ready" if unlocked and question_count else "practice_coming" if unlocked else "locked", "units": units})
        payload.append({"id": subject.id, "name": subject.name, "slug": subject.slug, "order": subject.order, "unlocked": unlocked, "topics": topics})
    return {"level": profile.level if profile else 1, "unlocked_subjects": unlocked_count, "subjects": payload}


@router.get("/next")
async def next_adaptive_problem(topic_id: int | None = None, unit: int | None = None, exclude_ids: str | None = None, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(GamificationProfile).filter_by(user_id=current_user.id).first()
    unlocked_ids = [row.id for row in db.query(Subject).filter(Subject.order < 900).order_by(Subject.order, Subject.id).limit(unlocked_subject_count(profile)).all()]
    recent_ids = [row.question_id for row in db.query(ProblemSubmission).filter_by(user_id=current_user.id).order_by(ProblemSubmission.submitted_at.desc()).limit(8).all()]
    mastery = {row.topic_id: row for row in db.query(MasteryRecord).filter_by(user_id=current_user.id).all()}
    candidate_query = db.query(Question).join(QuestionBank).join(Topic).filter(Topic.subject_id.in_(unlocked_ids), Question.is_published.is_(True))
    if topic_id is not None:
        selected_topic = db.query(Topic).filter(Topic.id == topic_id, Topic.subject_id.in_(unlocked_ids)).first()
        if selected_topic is None:
            raise HTTPException(status_code=404, detail="Topic is locked or does not exist")
        if unit is not None:
            if unit < 1 or unit > len(UNIT_STAGES):
                raise HTTPException(status_code=422, detail="Unknown unit")
            record = mastery.get(topic_id)
            required_attempts, required_mastery = UNIT_STAGES[unit - 1][2], UNIT_STAGES[unit - 1][3]
            if (record.times_practiced if record else 0) < required_attempts or (record.mastery_level if record else 0) < required_mastery:
                raise HTTPException(status_code=403, detail="Complete earlier units before opening this unit")
        candidate_query = candidate_query.filter(Topic.id == topic_id)
    excluded = {int(value) for value in (exclude_ids or "").split(",") if value.isdigit()}
    candidates = candidate_query.filter(Question.id.notin_(excluded)).all() if excluded else candidate_query.all()
    if not candidates and excluded:
        candidates = candidate_query.all()
    if not candidates:
        raise HTTPException(status_code=404, detail="No adaptive problems are available for this topic" if topic_id else "No adaptive problems are available for unlocked topics")
    accuracy = profile.accuracy_average if profile else 0
    unit_target = {1: "easy", 2: "easy", 3: "medium", 4: "hard"}.get(unit)
    preferred = unit_target or ("easy" if (profile is None or profile.problems_solved < 3 or accuracy < 55) else "hard" if accuracy >= 90 else "medium")
    difficulty_distance = {"introductory": {"easy": 0, "medium": 2, "hard": 3}, "easy": {"easy": 0, "medium": 1, "hard": 2}, "medium": {"easy": 1, "medium": 0, "hard": 1}, "hard": {"easy": 2, "medium": 1, "hard": 0}, "expert": {"easy": 3, "medium": 2, "hard": 1}}
    def priority(question: Question):
        record = mastery.get(question.question_bank.topic_id)
        level = record.mastery_level if record else 0
        target_gap = abs(level - 65)
        repeat_penalty = 100 if question.id in recent_ids else 0
        return repeat_penalty + difficulty_distance.get(question.difficulty.value, {}).get(preferred, 2) * 20 + target_gap
    ranked = sorted(candidates, key=priority)
    question = random.choice(ranked[:min(3, len(ranked))])
    topic = question.question_bank.topic
    return {"session_id": uuid.uuid4().hex, "unit": unit, "selection_reason": f"Selected inside {topic.name} for your current {preferred} difficulty target.", "question": {"id": question.id, "title": question.title, "content_html": question.content_html, "difficulty": question.difficulty.value, "question_type": question.question_type.value, "topic": topic.name, "subject": topic.subject.name, "accepted_units": question.accepted_units or [], "coding_language": question.coding_language, "starter_code": question.starter_code, "test_count": len(question.test_cases or [])}}
