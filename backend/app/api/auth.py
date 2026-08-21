"""
Authentication API routes.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.models import (
    User,
    GamificationProfile,
    UsageQuota,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    Quest,
    UserQuest,
)
from pydantic import BaseModel, EmailStr, Field, field_validator

router = APIRouter()


class UserRegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")
        return password


class UserLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=UserLoginResponse)
async def register(
    user_data: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """Register a new user."""
    # Check if user exists
    existing_user = db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.username)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already exists"
        )
    
    # Create new user
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        is_active=True,
    )
    
    db.add(user)
    db.flush()

    related = [
        GamificationProfile(user_id=user.id),
        UsageQuota(user_id=user.id),
        Subscription(
            user_id=user.id,
            plan=SubscriptionPlan.FREE,
            status=SubscriptionStatus.FREE,
        ),
    ]
    for quest in db.query(Quest).filter(Quest.quest_type == "daily").all():
        related.append(UserQuest(user_id=user.id, quest_id=quest.id, target=(quest.criteria or {}).get("target", 1)))
    db.add_all(related)
    db.commit()
    db.refresh(user)
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return UserLoginResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=UserLoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login with email/username and password."""
    user = db.query(User).filter(
        (User.email == form_data.username) | (User.username == form_data.username)
    ).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password"
        )

    user.last_login_at = datetime.utcnow()
    db.commit()
    
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return UserLoginResponse(access_token=access_token, refresh_token=refresh_token)


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=UserLoginResponse)
async def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token."""
    claims = decode_token(payload.refresh_token)
    user_id = claims.get("sub")
    user = db.query(User).filter(User.id == int(user_id), User.is_active.is_(True)).first() if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return UserLoginResponse(access_token=create_access_token({"sub": str(user.id)}), refresh_token=create_refresh_token({"sub": str(user.id)}))


@router.post("/logout")
async def logout():
    """Logout user."""
    return {"message": "Logged out successfully"}


@router.post("/forgot-password")
async def forgot_password(email: str, db: Session = Depends(get_db)):
    """Request password reset."""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return {"message": "If the account exists, a reset token has been issued"}
    token = create_access_token({"sub": str(user.id), "purpose": "password_reset"}, timedelta(minutes=15))
    return {"message": "If the account exists, a reset token has been issued", "reset_token": token}


@router.post("/reset-password")
async def reset_password(token: str, new_password: str, db: Session = Depends(get_db)):
    """Reset password with token."""
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    claims = decode_token(token)
    if claims.get("purpose") != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid password reset token")
    user = db.query(User).filter(User.id == int(claims["sub"]), User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid password reset token")
    user.hashed_password = hash_password(new_password)
    user.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Password reset successfully"}
