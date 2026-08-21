"""
Role-Based Access Control (RBAC) and permissions.
"""

from enum import Enum
from typing import List, Optional
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.core.database import get_db


class UserRole(str, Enum):
    """User roles in the system."""
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    ADMIN = "admin"


class Permission(str, Enum):
    """System permissions."""
    # Student permissions
    VIEW_COURSES = "view_courses"
    ENROLL_COURSE = "enroll_course"
    TAKE_QUIZ = "take_quiz"
    VIEW_GRADES = "view_grades"
    VIEW_PROGRESS = "view_progress"
    
    # Instructor permissions
    CREATE_COURSE = "create_course"
    EDIT_COURSE = "edit_course"
    DELETE_COURSE = "delete_course"
    VIEW_STUDENT_PROGRESS = "view_student_progress"
    VIEW_ANALYTICS = "view_analytics"
    
    # Admin permissions
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    MANAGE_COURSES = "manage_courses"
    VIEW_SYSTEM_ANALYTICS = "view_system_analytics"
    MANAGE_BILLING = "manage_billing"


# Role to permissions mapping
ROLE_PERMISSIONS = {
    UserRole.STUDENT: [
        Permission.VIEW_COURSES,
        Permission.ENROLL_COURSE,
        Permission.TAKE_QUIZ,
        Permission.VIEW_GRADES,
        Permission.VIEW_PROGRESS,
    ],
    UserRole.INSTRUCTOR: [
        Permission.VIEW_COURSES,
        Permission.ENROLL_COURSE,
        Permission.TAKE_QUIZ,
        Permission.VIEW_GRADES,
        Permission.VIEW_PROGRESS,
        Permission.CREATE_COURSE,
        Permission.EDIT_COURSE,
        Permission.DELETE_COURSE,
        Permission.VIEW_STUDENT_PROGRESS,
        Permission.VIEW_ANALYTICS,
    ],
    UserRole.ADMIN: [
        Permission.VIEW_COURSES,
        Permission.ENROLL_COURSE,
        Permission.TAKE_QUIZ,
        Permission.VIEW_GRADES,
        Permission.VIEW_PROGRESS,
        Permission.CREATE_COURSE,
        Permission.EDIT_COURSE,
        Permission.DELETE_COURSE,
        Permission.VIEW_STUDENT_PROGRESS,
        Permission.VIEW_ANALYTICS,
        Permission.MANAGE_USERS,
        Permission.MANAGE_ROLES,
        Permission.MANAGE_COURSES,
        Permission.VIEW_SYSTEM_ANALYTICS,
        Permission.MANAGE_BILLING,
    ],
}


def require_role(required_roles: List[UserRole]):
    """Dependency to check if user has required role."""
    async def check_role(
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        user_role = current_user.role
        if user_role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    
    return check_role


def require_permission(required_permission: Permission):
    """Dependency to check if user has required permission."""
    async def check_permission(
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        user_role = current_user.role
        permissions = ROLE_PERMISSIONS.get(user_role, [])
        
        if required_permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    
    return check_permission
