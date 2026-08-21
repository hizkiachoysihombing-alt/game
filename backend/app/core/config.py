"""
Backend configuration using environment variables.
"""

from typing import List
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings."""
    
    # App
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://electroquest:electroquest_dev@localhost:5432/electroquest_db"
    )
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "10"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))
    
    # CORS
    CORS_ORIGINS: List[str] = [origin.strip() for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000",
    ).split(",") if origin.strip()]
    
    # Authentication
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    
    # Email
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "noreply@electroquest.com")
    
    # Billing
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Learning Energy
    FREE_PLAN_DAILY_ENERGY: int = int(os.getenv("FREE_PLAN_DAILY_ENERGY", "25"))
    FREE_PLAN_ENERGY_RESET_HOUR: int = int(os.getenv("FREE_PLAN_ENERGY_RESET_HOUR", "0"))
    
    # Gamification
    BASE_XP_EASY: int = int(os.getenv("BASE_XP_EASY", "10"))
    BASE_XP_MEDIUM: int = int(os.getenv("BASE_XP_MEDIUM", "20"))
    BASE_XP_HARD: int = int(os.getenv("BASE_XP_HARD", "35"))
    BASE_XP_CHALLENGE: int = int(os.getenv("BASE_XP_CHALLENGE", "60"))
    LEVEL_UP_FORMULA: str = os.getenv("LEVEL_UP_FORMULA", "exponential")
    LEVEL_UP_FACTOR: float = float(os.getenv("LEVEL_UP_FACTOR", "1.5"))
    
    # Feature Flags
    ENABLE_CIRCUIT_LAB: bool = os.getenv("ENABLE_CIRCUIT_LAB", "false").lower() == "true"
    ENABLE_SINGLE_LINE_DIAGRAM: bool = os.getenv("ENABLE_SINGLE_LINE_DIAGRAM", "false").lower() == "true"
    ENABLE_POWER_FLOW: bool = os.getenv("ENABLE_POWER_FLOW", "false").lower() == "true"
    ENABLE_FAULT_ANALYSIS: bool = os.getenv("ENABLE_FAULT_ANALYSIS", "false").lower() == "true"
    ENABLE_AI_TUTOR: bool = os.getenv("ENABLE_AI_TUTOR", "false").lower() == "true"


settings = Settings()

if settings.APP_ENV == "production" and settings.SECRET_KEY == "your-super-secret-key-change-in-production":
    raise RuntimeError("SECRET_KEY must be explicitly configured in production")
