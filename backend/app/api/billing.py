"""
Billing and subscription API routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Subscription, SubscriptionPlan, SubscriptionStatus, SubscriptionPrice, UsageQuota

router = APIRouter()


@router.get("/plans")
async def list_subscription_plans(db: Session = Depends(get_db)):
    """List all subscription plans."""
    prices = db.query(SubscriptionPrice).filter(SubscriptionPrice.is_active.is_(True)).all()
    return [{"plan": item.plan.value, "currency": item.currency, "amount_cents": item.amount_cents, "billing_period": item.billing_period} for item in prices]


@router.get("/subscription")
async def get_subscription(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's subscription details."""
    subscription = db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    if subscription is None:
        subscription = Subscription(user_id=current_user.id, plan=SubscriptionPlan.FREE, status=SubscriptionStatus.FREE)
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
    return {"plan": subscription.plan.value, "status": subscription.status.value, "auto_renew": subscription.auto_renew, "current_period_end": subscription.current_period_end}


@router.post("/checkout")
async def create_checkout_session(
    plan_code: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a checkout session for subscription."""
    raise HTTPException(status_code=501, detail="Stripe checkout requires configured payment credentials")


@router.post("/webhook/stripe")
async def stripe_webhook(
    db: Session = Depends(get_db)
):
    """Handle Stripe webhook events."""
    raise HTTPException(status_code=501, detail="Stripe webhook is unavailable until Stripe is configured")


@router.post("/cancel")
async def cancel_subscription(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel subscription."""
    subscription = db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    subscription.auto_renew = False
    subscription.status = SubscriptionStatus.CANCELING if subscription.plan != SubscriptionPlan.FREE else SubscriptionStatus.FREE
    db.commit()
    return {"status": subscription.status.value, "auto_renew": subscription.auto_renew}


@router.post("/resume")
async def resume_subscription(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resume canceled subscription."""
    subscription = db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    subscription.auto_renew = True
    if subscription.plan != SubscriptionPlan.FREE:
        subscription.status = SubscriptionStatus.ACTIVE
    db.commit()
    return {"status": subscription.status.value, "auto_renew": subscription.auto_renew}


@router.get("/invoices")
async def get_invoices(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's invoices."""
    return []


@router.get("/usage")
async def get_usage(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's usage quota status (for Free users)."""
    quota = db.query(UsageQuota).filter(UsageQuota.user_id == current_user.id).first()
    if quota is None:
        quota = UsageQuota(user_id=current_user.id)
        db.add(quota)
        db.commit()
    return {"daily_limit": quota.daily_problems_limit, "daily_used": quota.daily_problems_used, "daily_remaining": max(0, quota.daily_problems_limit - quota.daily_problems_used), "monthly_limit": quota.monthly_problems_limit, "monthly_used": quota.monthly_problems_used}
