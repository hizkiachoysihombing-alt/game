"""
Admin API routes.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_role, UserRole
from app.models.models import User, Course, Enrollment, Subscription, PaymentTransaction

router = APIRouter()


class RoleUpdate(BaseModel):
    role: UserRole


@router.get("/users", dependencies=[Depends(require_role([UserRole.ADMIN]))])
async def list_users(db: Session = Depends(get_db)):
    """List all users (admin only)."""
    return [{"id": user.id, "email": user.email, "username": user.username, "full_name": user.full_name, "role": user.role.value, "is_active": user.is_active} for user in db.query(User).order_by(User.created_at.desc()).all()]


@router.get("/users/{user_id}", dependencies=[Depends(require_role([UserRole.ADMIN]))])
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user details (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user.id, "email": user.email, "username": user.username, "full_name": user.full_name, "role": user.role.value, "is_active": user.is_active, "created_at": user.created_at}


@router.post("/users/{user_id}/role", dependencies=[Depends(require_role([UserRole.ADMIN]))])
async def update_user_role(
    user_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db)
):
    """Update user's role (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = payload.role
    user.updated_at = datetime.utcnow()
    db.commit()
    return {"id": user.id, "role": user.role.value}


@router.get("/analytics", dependencies=[Depends(require_role([UserRole.ADMIN]))])
async def get_platform_analytics(db: Session = Depends(get_db)):
    """Get platform-wide analytics (admin only)."""
    return {"users": db.query(User).count(), "active_users": db.query(User).filter(User.is_active.is_(True)).count(), "published_courses": db.query(Course).filter(Course.is_published.is_(True)).count(), "enrollments": db.query(Enrollment).count()}


@router.get("/billing/analytics", dependencies=[Depends(require_role([UserRole.ADMIN]))])
async def get_billing_analytics(db: Session = Depends(get_db)):
    """Get billing analytics (admin only)."""
    return {"subscriptions": db.query(Subscription).count(), "payments": db.query(PaymentTransaction).count(), "successful_payments": db.query(PaymentTransaction).filter(PaymentTransaction.status == "succeeded").count()}


@router.get("/courses", dependencies=[Depends(require_role([UserRole.ADMIN]))])
async def list_all_courses(db: Session = Depends(get_db)):
    """List all courses (admin only)."""
    return [{"id": course.id, "name": course.name, "slug": course.slug, "is_published": course.is_published, "enrollments": len(course.enrollments)} for course in db.query(Course).order_by(Course.created_at.desc()).all()]


@router.post("/courses/{course_id}/publish", dependencies=[Depends(require_role([UserRole.ADMIN]))])
async def publish_course(course_id: int, db: Session = Depends(get_db)):
    """Publish a course (admin only)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    course.is_published = True
    course.updated_at = datetime.utcnow()
    db.commit()
    return {"id": course.id, "is_published": course.is_published}


@router.get("/audit-log", dependencies=[Depends(require_role([UserRole.ADMIN]))])
async def get_audit_log(db: Session = Depends(get_db)):
    """Get audit log (admin only)."""
    return {"entries": [], "message": "Audit events are not persisted in the foundation schema"}
