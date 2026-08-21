"""
Course and learning management API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Course, Subject, LearningPath

router = APIRouter()


def course_payload(course: Course, user_id: int | None = None) -> dict:
    return {
        "id": course.id,
        "name": course.name,
        "slug": course.slug,
        "description": course.description,
        "thumbnail_url": course.thumbnail_url,
        "difficulty": course.difficulty,
        "estimated_hours": course.estimated_hours,
        "is_enrolled": any(enrollment.student_id == user_id and enrollment.is_active for enrollment in course.enrollments) if user_id else False,
        "subject": {"id": course.subject.id, "name": course.subject.name} if course.subject else None,
        "modules": [
            {
                "id": module.id,
                "name": module.name,
                "order": module.order,
                "lessons": [
                    {"id": lesson.id, "name": lesson.name, "order": lesson.order}
                    for lesson in sorted(module.lessons, key=lambda item: item.order)
                    if lesson.is_published
                ],
            }
            for module in sorted(course.modules, key=lambda item: item.order)
        ],
    }


@router.get("/subjects/")
async def list_subjects(db: Session = Depends(get_db)):
    """List all subjects."""
    return [{"id": subject.id, "name": subject.name, "slug": subject.slug, "description": subject.description} for subject in db.query(Subject).order_by(Subject.order).all()]


@router.get("/learning-paths/")
async def list_learning_paths(db: Session = Depends(get_db)):
    """List all learning paths."""
    paths = db.query(LearningPath).filter(LearningPath.is_published.is_(True)).order_by(LearningPath.order).all()
    return [{"id": path.id, "name": path.name, "slug": path.slug, "description": path.description, "course_count": len(path.courses)} for path in paths]


@router.get("/")
async def list_courses(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """List all published courses."""
    courses = db.query(Course).options(joinedload(Course.subject), joinedload(Course.modules)).filter(Course.is_published.is_(True)).order_by(Course.order).all()
    return [course_payload(course, current_user.id) for course in courses]


@router.get("/{course_id}")
async def get_course(course_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Get course details."""
    course = db.query(Course).options(joinedload(Course.subject), joinedload(Course.modules)).filter(Course.id == course_id, Course.is_published.is_(True)).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course_payload(course, current_user.id)

