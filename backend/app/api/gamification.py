"""
Gamification API routes (XP, achievements, leaderboards, etc).
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.cache import cache_get, cache_set
from app.models.models import GamificationProfile, XPTransaction, Achievement, UserAchievement, Leaderboard, ProblemSubmission, Question, Quest, UserQuest, User

router = APIRouter()


def submission_rankings(db: Session, period: str) -> list[dict]:
    """Rebuild daily/monthly rankings from verified attempts, including historic ones."""
    now = datetime.utcnow()
    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "monthly":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return []
    attempts = db.query(ProblemSubmission, Question).join(Question, Question.id == ProblemSubmission.question_id).filter(
        ProblemSubmission.submitted_at >= start,
        ProblemSubmission.submitted_at <= now,
    ).order_by(ProblemSubmission.user_id, ProblemSubmission.submitted_at).all()
    scores: dict[int, int] = {}
    attempt_counts: dict[int, int] = {}
    for submission, question in attempts:
        attempt_counts[submission.user_id] = attempt_counts.get(submission.user_id, 0) + 1
        if attempt_counts[submission.user_id] > 20 or not submission.is_correct:
            continue
        base = {"introductory": 20, "easy": 30, "medium": 45, "hard": 65, "expert": 85}.get(question.difficulty.value, 30)
        answer = submission.answer if isinstance(submission.answer, dict) else {}
        response_time = answer.get("response_time_seconds")
        speed_bonus = 0 if response_time is None else max(0, min(15, round(15 - float(response_time) / 4)))
        scores[submission.user_id] = scores.get(submission.user_id, 0) + base + speed_bonus
    users = {user.id: user for user in db.query(User).filter(User.id.in_(scores.keys())).all()} if scores else {}
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [{"user_id": user_id, "username": users[user_id].username, "full_name": users[user_id].full_name, "rank": rank, "score": score} for rank, (user_id, score) in enumerate(ordered[:100], start=1) if user_id in users]


@router.get("/profile")
async def get_gamification_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's gamification profile (XP, level, coins, streaks)."""
    profile = db.query(GamificationProfile).filter(GamificationProfile.user_id == current_user.id).first()
    if profile is None:
        profile = GamificationProfile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return {"user_id": current_user.id, "total_xp": profile.total_xp, "level": profile.level, "xp_to_next_level": profile.xp_to_next_level, "coins": profile.coins, "current_streak_days": profile.current_streak_days, "longest_streak_days": profile.longest_streak_days, "problems_solved": profile.problems_solved, "accuracy_average": profile.accuracy_average}


@router.get("/achievements")
async def get_achievements(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's achievements and progress."""
    earned = db.query(UserAchievement).filter(UserAchievement.user_id == current_user.id).all()
    earned_ids = {item.achievement_id for item in earned}
    achievements = db.query(Achievement).all()
    return [{"id": item.id, "name": item.name, "slug": item.slug, "description": item.description, "rarity": item.rarity, "xp_reward": item.xp_reward, "earned": item.id in earned_ids} for item in achievements]


@router.get("/leaderboard")
async def get_leaderboard(
    period: str = "weekly",
    category: str = "ranked_engineering",
    db: Session = Depends(get_db)
):
    """Get leaderboard."""
    if period not in {"daily", "weekly", "monthly"}:
        raise HTTPException(status_code=422, detail="Unsupported leaderboard period")
    cache_key = f"leaderboard:{period}:{category}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached
    if period in {"daily", "monthly"}:
        payload = submission_rankings(db, period)
        await cache_set(cache_key, payload, ttl=10)
        return payload
    query = db.query(Leaderboard, User).join(User, User.id == Leaderboard.user_id).filter(Leaderboard.period == period, Leaderboard.category == category)
    if period == "weekly":
        now = datetime.utcnow()
        week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(Leaderboard.updated_at >= week_start)
    entries = query.order_by(Leaderboard.score.desc(), Leaderboard.updated_at).limit(100).all()
    payload = [{"user_id": item.user_id, "username": user.username, "full_name": user.full_name, "rank": rank, "score": item.score} for rank, (item, user) in enumerate(entries, start=1)]
    await cache_set(cache_key, payload, ttl=10)
    return payload


@router.get("/daily-quests")
async def get_daily_quests(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get daily quests."""
    quests = db.query(Quest).filter(Quest.quest_type == "daily").all()
    existing = {item.quest_id: item for item in db.query(UserQuest).filter(UserQuest.user_id == current_user.id).all()}
    for quest in quests:
        if quest.id not in existing:
            item = UserQuest(user_id=current_user.id, quest_id=quest.id, target=(quest.criteria or {}).get("target", 1))
            db.add(item)
            db.flush()
            existing[quest.id] = item
    db.commit()
    return [{"id": item.id, "quest_id": item.quest_id, "name": item.quest.name, "description": item.quest.description, "progress": item.progress, "target": item.target, "xp_reward": item.quest.xp_reward, "coin_reward": item.quest.coin_reward, "completed": item.completed_at is not None} for item in existing.values() if item.quest.quest_type == "daily"]


@router.post("/daily-quests/{quest_id}/complete")
async def complete_quest(
    quest_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Quest completion is awarded only from verified backend events."""
    quest = db.query(UserQuest).filter(UserQuest.id == quest_id, UserQuest.user_id == current_user.id).first()
    if quest is None:
        raise HTTPException(status_code=404, detail="Quest not found")
    if quest.completed_at is None:
        raise HTTPException(status_code=409, detail="Quest target has not been reached")
    return {"id": quest.id, "completed": True, "completed_at": quest.completed_at}


@router.get("/xp-history")
async def get_xp_history(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's XP transaction history."""
    transactions = db.query(XPTransaction).filter(XPTransaction.user_id == current_user.id).order_by(XPTransaction.created_at.desc()).limit(100).all()
    return [{"id": item.id, "amount": item.amount, "reason": item.reason, "related_id": item.related_id, "created_at": item.created_at} for item in transactions]
