"""Aggregated student dashboard endpoint."""

from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user
from app.models.models import FriendStreak, MasteryRecord, ProblemSubmission, ReasoningDiagnosis, Subscription, SubscriptionPlan, Topic, UsageQuota, User, UserQuest
from app.services.progress import get_profile

router = APIRouter()


class FriendStreakCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)


def activity_dates(db: Session, user_id: int, days: int = 120) -> set[date]:
    cutoff = date.today() - timedelta(days=days)
    rows = db.query(ProblemSubmission.submitted_at).filter(
        ProblemSubmission.user_id == user_id,
        ProblemSubmission.submitted_at.isnot(None),
        ProblemSubmission.submitted_at >= cutoff,
    ).all()
    return {row[0].date() for row in rows}


def consecutive_days(dates: set[date]) -> int:
    cursor = date.today()
    if cursor not in dates:
        cursor -= timedelta(days=1)
    count = 0
    while cursor in dates:
        count += 1
        cursor -= timedelta(days=1)
    return count


def streak_payload(db: Session, current_user: User) -> dict:
    mine = activity_dates(db, current_user.id)
    connections = db.query(FriendStreak).filter(or_(
        FriendStreak.user_low_id == current_user.id,
        FriendStreak.user_high_id == current_user.id,
    )).all()
    friends = []
    for connection in connections:
        friend_id = connection.user_high_id if connection.user_low_id == current_user.id else connection.user_low_id
        friend = db.query(User).filter_by(id=friend_id, is_active=True).first()
        if not friend:
            continue
        shared = mine & activity_dates(db, friend_id)
        friends.append({
            "id": friend.id,
            "full_name": friend.full_name,
            "username": friend.username,
            "avatar_url": friend.avatar_url,
            "shared_streak_days": consecutive_days(shared),
            "active_today": date.today() in shared,
        })
    return {
        "activity_dates": sorted(item.isoformat() for item in mine),
        "friends": sorted(friends, key=lambda item: item["shared_streak_days"], reverse=True),
    }


@router.get("/streak")
async def get_streak(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return streak_payload(db, current_user)


@router.post("/streak/friends", status_code=201)
async def add_streak_friend(payload: FriendStreakCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    friend = db.query(User).filter(func.lower(User.username) == payload.username.strip().lower(), User.is_active.is_(True)).first()
    if not friend:
        raise HTTPException(status_code=404, detail="Username tidak ditemukan")
    if friend.id == current_user.id:
        raise HTTPException(status_code=400, detail="Tidak dapat membuat runtunan dengan akun sendiri")
    low_id, high_id = sorted((current_user.id, friend.id))
    existing = db.query(FriendStreak).filter_by(user_low_id=low_id, user_high_id=high_id).first()
    if not existing:
        db.add(FriendStreak(user_low_id=low_id, user_high_id=high_id))
        db.commit()
    return streak_payload(db, current_user)


@router.get("/student")
async def student_dashboard(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    profile = get_profile(db, current_user.id)
    quota = db.query(UsageQuota).filter_by(user_id=current_user.id).first()
    if quota and quota.daily_problems_limit < settings.FREE_PLAN_DAILY_ENERGY:
        quota.daily_problems_limit = settings.FREE_PLAN_DAILY_ENERGY
    subscription = db.query(Subscription).filter_by(user_id=current_user.id).first()
    mastery_rows = db.query(MasteryRecord, Topic).join(Topic).filter(MasteryRecord.user_id == current_user.id).all()
    diagnoses = db.query(ReasoningDiagnosis).filter_by(user_id=current_user.id, error_detected=True).order_by(ReasoningDiagnosis.created_at.desc()).limit(5).all()
    quests = db.query(UserQuest).filter_by(user_id=current_user.id).order_by(UserQuest.assigned_at.desc()).limit(5).all()
    unlimited_energy = bool(subscription and subscription.plan != SubscriptionPlan.FREE)
    energy_limit = None if unlimited_energy else (quota.daily_problems_limit if quota else settings.FREE_PLAN_DAILY_ENERGY)
    remaining = None if unlimited_energy else max(0, energy_limit - (quota.daily_problems_used if quota else 0))
    overall_mastery = round(sum(record.mastery_level for record, _ in mastery_rows) / len(mastery_rows), 1) if mastery_rows else 0
    db.commit()
    return {
        "student": {"id": current_user.id, "full_name": current_user.full_name, "avatar_url": current_user.avatar_url},
        "gamification": {"level": profile.level, "rank": "Apprentice Engineer" if profile.level < 5 else "Circuit Analyst", "total_xp": profile.total_xp, "xp_to_next_level": profile.xp_to_next_level, "coins": profile.coins, "current_streak_days": profile.current_streak_days, "longest_streak_days": profile.longest_streak_days, "problems_solved": profile.problems_solved, "accuracy_average": profile.accuracy_average},
        "subscription": {"plan": subscription.plan.value if subscription else "free", "energy_remaining": remaining, "energy_limit": energy_limit},
        "mastery": {"overall": overall_mastery, "topics": [{"topic_id": topic.id, "name": topic.name, "level": record.mastery_level, "needs_review": record.needs_review} for record, topic in mastery_rows]},
        "quests": [{"id": item.id, "name": item.quest.name, "progress": item.progress, "target": item.target, "completed": item.completed_at is not None} for item in quests],
        "recent_errors": [{"type": item.error_type.value if item.error_type else "other", "analysis": item.analysis, "recommended_review": item.recommended_review} for item in diagnoses],
        "next_action": "Continue your adaptive Journey and strengthen the topics that need review",
    }
