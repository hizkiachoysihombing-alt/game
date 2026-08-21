"""
User management API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.security import hash_password, verify_password
from app.models.models import User

router = APIRouter()


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    username: str | None = Field(default=None, min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str | None = Field(default=None, min_length=5, max_length=255)
    bio: str | None = None
    institution: str | None = Field(default=None, max_length=255)
    major: str | None = Field(default=None, max_length=255)
    semester: int | None = Field(default=None, ge=1, le=20)
    avatar_url: str | None = Field(default=None, max_length=512)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "role": user.role.value,
        "is_verified": user.is_verified,
        "bio": user.bio,
        "institution": user.institution,
        "major": user.major,
        "semester": user.semester,
        "created_at": user.created_at,
    }


@router.get("/me")
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's profile."""
    return serialize_user(current_user)


@router.get("/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID."""
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_user(user)


@router.put("/me")
async def update_profile(
    profile: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile."""
    changes = profile.model_dump(exclude_unset=True)
    if changes.get("username"):
        username = changes["username"].strip()
        duplicate = db.query(User).filter(func.lower(User.username) == username.lower(), User.id != current_user.id).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Username is already in use")
        changes["username"] = username
    if changes.get("email"):
        email = changes["email"].strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise HTTPException(status_code=422, detail="Enter a valid email address")
        duplicate = db.query(User).filter(func.lower(User.email) == email, User.id != current_user.id).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Email is already in use")
        changes["email"] = email
    for field, value in changes.items():
        setattr(current_user, field, value)
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    return serialize_user(current_user)


@router.put("/me/password")
async def change_password(
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change password."""
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Password updated successfully"}
