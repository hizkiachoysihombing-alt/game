"""Authoritative gamification, mastery, quest, and diagnosis updates."""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.models import (
    Achievement, GamificationProfile, Leaderboard, MasteryRecord, ProblemSubmission, Question, ReasoningDiagnosis,
    ReasoningErrorType, UserAchievement, UserQuest, XPTransaction,
)


ERROR_TYPES = {
    "UNIT_CONVERSION_ERROR": ReasoningErrorType.UNIT_CONVERSION_ERROR,
    "ARITHMETIC_ERROR": ReasoningErrorType.ARITHMETIC_ERROR,
    "CONCEPTUAL_MISUNDERSTANDING": ReasoningErrorType.CONCEPTUAL_MISUNDERSTANDING,
}


def get_profile(db: Session, user_id: int) -> GamificationProfile:
    profile = db.query(GamificationProfile).filter_by(user_id=user_id).first()
    if profile is None:
        profile = GamificationProfile(user_id=user_id)
        db.add(profile)
        db.flush()
    return profile


def record_activity(profile: GamificationProfile, correct: bool) -> None:
    now = datetime.utcnow()
    today = now.date()
    previous = profile.last_activity_date.date() if profile.last_activity_date else None
    if previous != today:
        profile.current_streak_days = (profile.current_streak_days + 1) if previous == today - timedelta(days=1) else 1
        profile.longest_streak_days = max(profile.longest_streak_days, profile.current_streak_days)
    profile.last_activity_date = now
    old_total = profile.problems_solved
    profile.problems_solved += 1
    old_correct = (profile.accuracy_average or 0.0) * old_total / 100
    profile.accuracy_average = ((old_correct + int(correct)) / profile.problems_solved) * 100


def grant_xp(db: Session, profile: GamificationProfile, amount: int, reason: str, related_id: int) -> None:
    if amount <= 0:
        return
    profile.total_xp += amount
    profile.level = profile.total_xp // 100 + 1
    profile.xp_to_next_level = profile.level * 100 - profile.total_xp
    profile.coins += max(1, amount // 5)
    db.add(XPTransaction(user_id=profile.user_id, amount=amount, reason=reason, related_id=related_id))


def update_mastery(db: Session, user_id: int, question: Question, correct: bool) -> MasteryRecord:
    topic_id = question.question_bank.topic_id
    record = db.query(MasteryRecord).filter_by(user_id=user_id, topic_id=topic_id).first()
    if record is None:
        record = MasteryRecord(
            user_id=user_id, topic_id=topic_id, mastery_level=0.0,
            confidence=0.0, times_practiced=0, times_correct=0,
            is_struggling=False, needs_review=False, mastered=False,
        )
        db.add(record)
    record.times_practiced += 1
    record.times_correct += int(correct)
    accuracy = record.times_correct / record.times_practiced
    difficulty_weight = {"introductory": 0.8, "easy": 0.9, "medium": 1.0, "hard": 1.1, "expert": 1.2}.get(question.difficulty.value, 1.0)
    evidence = min(1.0, record.times_practiced / 10)
    record.mastery_level = round(min(100.0, accuracy * 100 * difficulty_weight), 2)
    record.confidence = round(evidence * 100, 2)
    record.recent_accuracy = round(accuracy * 100, 2)
    record.is_struggling = record.times_practiced >= 3 and accuracy < 0.5
    record.needs_review = not correct or record.mastery_level < 70
    record.mastered = record.times_practiced >= 5 and record.mastery_level >= 85
    record.last_practiced_at = datetime.utcnow()
    return record


def record_diagnosis(db: Session, user_id: int, submission_id: int, error_code: str | None, feedback: str, topic_name: str) -> ReasoningDiagnosis | None:
    if not error_code:
        return None
    diagnosis = ReasoningDiagnosis(
        user_id=user_id, submission_id=submission_id, error_detected=True,
        error_type=ERROR_TYPES.get(error_code, ReasoningErrorType.OTHER),
        analysis=feedback, confidence_score=0.75,
        recommended_review=f"Review {topic_name}", recommended_practice_type="targeted_practice",
    )
    db.add(diagnosis)
    return diagnosis


def update_quests(db: Session, user_id: int) -> None:
    quests = db.query(UserQuest).filter(UserQuest.user_id == user_id, UserQuest.completed_at.is_(None)).all()
    for user_quest in quests:
        criteria = user_quest.quest.criteria or {}
        if criteria.get("event") != "problem_submitted":
            continue
        user_quest.progress = min(user_quest.target or 1, user_quest.progress + 1)
        if user_quest.progress >= (user_quest.target or 1):
            user_quest.completed_at = datetime.utcnow()
            profile = get_profile(db, user_id)
            grant_xp(db, profile, user_quest.quest.xp_reward or 0, "quest_completed", user_quest.quest_id)
            profile.coins += user_quest.quest.coin_reward or 0


def evaluate_achievements(db: Session, user_id: int) -> None:
    profile = get_profile(db, user_id)
    earned = {row.achievement_id for row in db.query(UserAchievement).filter_by(user_id=user_id).all()}
    for achievement in db.query(Achievement).all():
        criteria = achievement.criteria or {}
        value = getattr(profile, criteria.get("field", ""), 0)
        if achievement.id not in earned and value >= criteria.get("target", 10**9):
            db.add(UserAchievement(user_id=user_id, achievement_id=achievement.id))
            grant_xp(db, profile, achievement.xp_reward or 0, "achievement_earned", achievement.id)
            profile.coins += achievement.coin_reward or 0


def update_ranked_score(db: Session, user_id: int, question: Question, correct: bool, response_time_seconds: float | None) -> int:
    """Score only the first 20 ranked attempts to keep Free and Pro competition fair."""
    now = datetime.utcnow()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    attempts = db.query(ProblemSubmission).filter(ProblemSubmission.user_id == user_id, ProblemSubmission.submitted_at >= week_start).count()
    if not correct or attempts > 20:
        return 0
    base = {"introductory": 20, "easy": 30, "medium": 45, "hard": 65, "expert": 85}.get(question.difficulty.value, 30)
    speed_bonus = 0 if response_time_seconds is None else max(0, min(15, round(15 - response_time_seconds / 4)))
    points = base + speed_bonus
    entry = db.query(Leaderboard).filter_by(user_id=user_id, period="weekly", category="ranked_engineering").first()
    if entry is None:
        entry = Leaderboard(user_id=user_id, period="weekly", category="ranked_engineering", score=0)
        db.add(entry)
    elif entry.updated_at < week_start:
        entry.score = 0
    entry.score = (entry.score or 0) + points
    return points
