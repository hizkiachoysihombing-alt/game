"""
SQLAlchemy models for ElectroQuest.

Complete data models covering:
- User management and RBAC
- Courses and learning paths
- Lessons and content
- Questions and assessments
- Gamification system
- Mastery and progress tracking
- Subscriptions and billing
- Usage quotas
- Reasoning diagnosis
"""

from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, Enum, JSON, Table, UniqueConstraint
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum

from app.core.database import Base
from app.core.permissions import UserRole


# ============================================================================
# USER & AUTHENTICATION
# ============================================================================

class User(Base):
    """User model representing all system users."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    avatar_url = Column(String(512))
    
    # Roles
    role = Column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime, nullable=True)
    
    # Profile
    bio = Column(Text)
    institution = Column(String(255))
    major = Column(String(255))
    semester = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    
    # Relationships
    student_enrollments = relationship("Enrollment", back_populates="student", foreign_keys="Enrollment.student_id")
    course_instructors = relationship("Course", back_populates="instructor")
    gamification_profile = relationship("GamificationProfile", uselist=False, back_populates="user")
    mastery_records = relationship("MasteryRecord", back_populates="user")
    subscription = relationship("Subscription", uselist=False, back_populates="user")
    usage_quota = relationship("UsageQuota", uselist=False, back_populates="user")
    xp_transactions = relationship("XPTransaction", back_populates="user")
    problem_submissions = relationship("ProblemSubmission", back_populates="user")
    reasoning_diagnoses = relationship("ReasoningDiagnosis", back_populates="user")
    
    __table_args__ = (
        UniqueConstraint("email", name="uq_user_email"),
        UniqueConstraint("username", name="uq_user_username"),
    )


# ============================================================================
# COURSES & LEARNING PATHS
# ============================================================================

class Subject(Base):
    """Subject categories (e.g., Circuit Analysis, Power Systems)."""
    __tablename__ = "subjects"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    icon = Column(String(50))
    order = Column(Integer, default=0)
    curriculum_code = Column(String(20), nullable=True)
    semester = Column(Integer, nullable=True)
    credits = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    courses = relationship("Course", back_populates="subject")
    topics = relationship("Topic", back_populates="subject")
    learning_paths = relationship("LearningPath", back_populates="subject")


class LearningPath(Base):
    """Curated learning paths combining multiple courses."""
    __tablename__ = "learning_paths"
    
    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text)
    difficulty = Column(String(20))  # beginner, intermediate, advanced
    estimated_hours = Column(Integer)
    order = Column(Integer, default=0)
    is_published = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    subject = relationship("Subject", back_populates="learning_paths")
    courses = relationship("Course", secondary="learning_path_courses", back_populates="learning_paths")
    prerequisites = relationship(
        "LearningPath",
        secondary="learning_path_prerequisites",
        primaryjoin="LearningPath.id == learning_path_prerequisites.c.learning_path_id",
        secondaryjoin="LearningPath.id == learning_path_prerequisites.c.prerequisite_id",
        backref="dependent_paths",
    )


class Course(Base):
    """Courses within subjects."""
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    instructor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text)
    thumbnail_url = Column(String(512))
    difficulty = Column(String(20))  # beginner, intermediate, advanced
    estimated_hours = Column(Integer)
    order = Column(Integer, default=0)
    is_published = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    subject = relationship("Subject", back_populates="courses")
    instructor = relationship("User", back_populates="course_instructors")
    modules = relationship("Module", back_populates="course", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")
    learning_paths = relationship("LearningPath", secondary="learning_path_courses", back_populates="courses")


class Module(Base):
    """Modules within courses."""
    __tablename__ = "modules"
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    name = Column(String(200), nullable=False)
    order = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    course = relationship("Course", back_populates="modules")
    lessons = relationship("Lesson", back_populates="module", cascade="all, delete-orphan")


class Lesson(Base):
    """Lessons within modules."""
    __tablename__ = "lessons"
    
    id = Column(Integer, primary_key=True)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False)
    name = Column(String(200), nullable=False)
    content_html = Column(Text)  # Rich HTML content
    order = Column(Integer, default=0)
    is_published = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    module = relationship("Module", back_populates="lessons")
    lesson_progress = relationship("LessonProgress", back_populates="lesson", cascade="all, delete-orphan")


class Enrollment(Base):
    """Course enrollments."""
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_enrollment_student_course"),
    )
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    enrolled_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    student = relationship("User", back_populates="student_enrollments", foreign_keys=[student_id])
    course = relationship("Course", back_populates="enrollments")


# ============================================================================
# LESSONS & PROGRESS
# ============================================================================

class LessonProgress(Base):
    """Student progress through lessons."""
    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress_user_lesson"),
    )
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    last_viewed_at = Column(DateTime, nullable=True)
    
    # Relationships
    lesson = relationship("Lesson", back_populates="lesson_progress")


# ============================================================================
# TOPICS & SKILLS
# ============================================================================

class Topic(Base):
    """Topics within subjects (used for mastery tracking)."""
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("subject_id", "slug", name="uq_topic_subject_slug"),
    )
    
    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    name = Column(String(150), nullable=False)
    slug = Column(String(150), nullable=False, index=True)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey("topics.id"), nullable=True)  # For hierarchical topics
    
    # Relationships
    subject = relationship("Subject", back_populates="topics")
    concept_tags = relationship("ConceptTag", back_populates="topic")
    mastery_records = relationship("MasteryRecord", back_populates="topic")


class ConceptTag(Base):
    """Concept tags for questions (e.g., "Ohm's Law", "KVL")."""
    __tablename__ = "concept_tags"
    
    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, index=True)
    
    # Relationships
    topic = relationship("Topic", back_populates="concept_tags")
    questions = relationship("Question", secondary="question_concepts", back_populates="concepts")
    misconceptions = relationship("Misconception", back_populates="concept")


# ============================================================================
# QUESTIONS & ASSESSMENTS
# ============================================================================

class QuestionDifficulty(str, PyEnum):
    INTRODUCTORY = "introductory"
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class QuestionType(str, PyEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    NUMERICAL = "numerical"
    MULTI_STEP = "multi_step"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"
    CALCULATION = "calculation"
    CIRCUIT = "circuit"
    SINGLE_LINE = "single_line"


class Question(Base):
    """Questions in the question bank."""
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True)
    question_bank_id = Column(Integer, ForeignKey("question_banks.id"), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    question_type = Column(Enum(QuestionType), nullable=False)
    difficulty = Column(Enum(QuestionDifficulty), default=QuestionDifficulty.MEDIUM, nullable=False)
    
    # Content
    content_html = Column(Text, nullable=False)  # Question statement
    solution_html = Column(Text)  # Worked solution
    explanation = Column(Text)  # Educational explanation
    
    # Metadata
    bloom_level = Column(String(50))  # remember, understand, apply, analyze, evaluate, create
    estimated_time_minutes = Column(Integer, default=5)
    xp_reward = Column(Integer)
    
    # For numerical questions
    expected_answer = Column(String(255))  # For matching/comparison
    numerical_tolerance = Column(Float)  # For acceptance range
    accepted_units = Column(JSON)  # List of acceptable units

    # For interactive programming questions. Test cases contain declarative,
    # non-executable source requirements so user code never runs in the API process.
    coding_language = Column(String(50))
    starter_code = Column(Text)
    test_cases = Column(JSON)
    
    # Tracking
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Instructor who created it
    is_published = Column(Boolean, default=False)
    times_answered = Column(Integer, default=0)
    average_accuracy = Column(Float)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    question_bank = relationship("QuestionBank", back_populates="questions")
    concepts = relationship("ConceptTag", secondary="question_concepts", back_populates="questions")
    misconceptions = relationship("Misconception", back_populates="question")
    submissions = relationship("ProblemSubmission", back_populates="question")
    answers = relationship("QuestionAnswer", back_populates="question", cascade="all, delete-orphan")


class QuestionBank(Base):
    """Organization of questions by topic."""
    __tablename__ = "question_banks"
    
    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Relationships
    topic = relationship("Topic")
    questions = relationship("Question", back_populates="question_bank")


class QuestionAnswer(Base):
    """Answer options for multiple-choice questions."""
    __tablename__ = "question_answers"
    
    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    text = Column(String(500), nullable=False)
    is_correct = Column(Boolean, default=False)
    order = Column(Integer, default=0)
    explanation = Column(Text)  # Why this answer is correct/incorrect
    
    # Relationships
    question = relationship("Question", back_populates="answers")


class Quiz(Base):
    """Quizzes combining multiple questions."""
    __tablename__ = "quizzes"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    is_published = Column(Boolean, default=False)
    
    # Timing
    time_limit_minutes = Column(Integer)
    shuffle_questions = Column(Boolean, default=True)
    show_correct_answer = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    questions = relationship("Question", secondary="quiz_questions", back_populates="quizzes")
    submissions = relationship("QuizSubmission", back_populates="quiz")


class Misconception(Base):
    """Common misconceptions for a concept/question."""
    __tablename__ = "misconceptions"
    
    id = Column(Integer, primary_key=True)
    concept_id = Column(Integer, ForeignKey("concept_tags.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    incorrect_answer = Column(String(255))  # Typical wrong answer
    remediation = Column(Text)  # How to address this misconception
    
    # Relationships
    concept = relationship("ConceptTag", back_populates="misconceptions")
    question = relationship("Question", back_populates="misconceptions")
    reasoning_errors = relationship("ReasoningError", back_populates="misconception")


# ============================================================================
# PROBLEM SUBMISSIONS & ASSESSMENT
# ============================================================================

class ProblemSubmissionStatus(str, PyEnum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADED = "graded"
    REVIEWED = "reviewed"


class ProblemSubmission(Base):
    """Student submissions to problems."""
    __tablename__ = "problem_submissions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    session_id = Column(String(100), unique=True, nullable=False, index=True)  # Idempotency key
    
    # Submission data
    answer = Column(JSON)  # Student's answer(s)
    working_notes = Column(Text)  # Student's work/reasoning
    status = Column(Enum(ProblemSubmissionStatus), default=ProblemSubmissionStatus.STARTED, nullable=False)
    
    # Grading
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float)  # 0-100
    xp_awarded = Column(Integer, default=0)
    feedback = Column(Text)
    attempted_count = Column(Integer, default=1)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    graded_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="problem_submissions")
    question = relationship("Question", back_populates="submissions")
    reasoning_diagnoses = relationship("ReasoningDiagnosis", back_populates="submission")


class QuizSubmission(Base):
    """Quiz attempts by students."""
    __tablename__ = "quiz_submissions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    
    # Results
    score = Column(Float)
    correct_count = Column(Integer)
    total_questions = Column(Integer)
    accuracy = Column(Float)  # correct_count / total_questions
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    time_taken_seconds = Column(Integer)
    
    # Relationships
    quiz = relationship("Quiz", back_populates="submissions")


# ============================================================================
# GAMIFICATION
# ============================================================================

class GamificationProfile(Base):
    """User's gamification stats and progress."""
    __tablename__ = "gamification_profiles"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Progression
    total_xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    xp_to_next_level = Column(Integer, default=100)
    
    # Coins
    coins = Column(Integer, default=0)
    
    # Streaks
    current_streak_days = Column(Integer, default=0)
    longest_streak_days = Column(Integer, default=0)
    last_activity_date = Column(DateTime, nullable=True)
    
    # Progress
    problems_solved = Column(Integer, default=0)
    quizzes_completed = Column(Integer, default=0)
    accuracy_average = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", uselist=False, back_populates="gamification_profile")


class FriendStreak(Base):
    """A symmetric learning-streak connection between two students."""
    __tablename__ = "friend_streaks"

    id = Column(Integer, primary_key=True)
    user_low_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_high_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id", name="uq_friend_streak_pair"),
    )


class XPTransaction(Base):
    """Immutable ledger of XP changes."""
    __tablename__ = "xp_transactions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=False)  # e.g., "problem_solved", "quest_completed"
    related_id = Column(Integer)  # ID of related object (question, quest, etc.)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="xp_transactions")


class Achievement(Base):
    """Achievement definitions."""
    __tablename__ = "achievements"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    icon_url = Column(String(512))
    rarity = Column(String(20))  # common, rare, epic, legendary
    xp_reward = Column(Integer, default=0)
    coin_reward = Column(Integer, default=0)
    
    # Criteria
    criteria = Column(JSON)  # Configurable criteria definition


class UserAchievement(Base):
    """User's earned achievements."""
    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    earned_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Quest(Base):
    """Daily and weekly quests."""
    __tablename__ = "quests"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    quest_type = Column(String(20))  # daily, weekly, event
    criteria = Column(JSON)  # Configurable criteria
    xp_reward = Column(Integer)
    coin_reward = Column(Integer)
    difficulty = Column(String(20))


class UserQuest(Base):
    """User's quest progress."""
    __tablename__ = "user_quests"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    progress = Column(Integer, default=0)
    target = Column(Integer)

    quest = relationship("Quest")


class Leaderboard(Base):
    """Leaderboard entries."""
    __tablename__ = "leaderboards"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    period = Column(String(50))  # daily, weekly, monthly, all_time
    category = Column(String(100))  # overall_xp, subject_name, etc.
    rank = Column(Integer)
    score = Column(Integer)  # XP or custom score
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ============================================================================
# MASTERY & PROGRESS TRACKING
# ============================================================================

class MasteryRecord(Base):
    """Student's mastery level for each topic/concept."""
    __tablename__ = "mastery_records"
    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_mastery_user_topic"),
    )
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    
    # Mastery measurement
    mastery_level = Column(Float, default=0.0)  # 0-100%
    confidence = Column(Float, default=0.0)  # Estimation confidence
    times_practiced = Column(Integer, default=0)
    times_correct = Column(Integer, default=0)
    recent_accuracy = Column(Float)  # Last N attempts
    
    # Flags
    is_struggling = Column(Boolean, default=False)
    needs_review = Column(Boolean, default=False)
    mastered = Column(Boolean, default=False)
    
    last_practiced_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="mastery_records")
    topic = relationship("Topic", back_populates="mastery_records")


# ============================================================================
# REASONING & DIAGNOSIS
# ============================================================================

class ReasoningErrorType(str, PyEnum):
    CONCEPTUAL_MISUNDERSTANDING = "conceptual_misunderstanding"
    FORMULA_SELECTION_ERROR = "formula_selection_error"
    WRONG_QUANTITY_SUBSTITUTION = "wrong_quantity_substitution"
    UNIT_CONVERSION_ERROR = "unit_conversion_error"
    ARITHMETIC_ERROR = "arithmetic_error"
    SIGN_CONVENTION_ERROR = "sign_convention_error"
    CIRCUIT_TOPOLOGY_ERROR = "circuit_topology_error"
    PHASE_LINE_CONFUSION = "phase_line_confusion"
    STAR_DELTA_CONFUSION = "star_delta_confusion"
    POWER_FACTOR_ERROR = "power_factor_error"
    PER_UNIT_ERROR = "per_unit_error"
    GUESSING = "guessing"
    OTHER = "other"


class ReasoningDiagnosis(Base):
    """Analysis of student's reasoning for a problem."""
    __tablename__ = "reasoning_diagnoses"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    submission_id = Column(Integer, ForeignKey("problem_submissions.id"), nullable=False)
    
    # Diagnosis
    error_detected = Column(Boolean, default=False)
    error_type = Column(Enum(ReasoningErrorType), nullable=True)
    misconception_id = Column(Integer, ForeignKey("misconceptions.id"), nullable=True)
    
    # Analysis
    analysis = Column(Text)  # Human-readable diagnosis
    confidence_score = Column(Float)  # 0-1 confidence in diagnosis
    
    # Recommendation
    recommended_review = Column(Text)
    recommended_practice_type = Column(String(100))
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="reasoning_diagnoses")
    submission = relationship("ProblemSubmission", back_populates="reasoning_diagnoses")
    misconception = relationship("Misconception", foreign_keys=[misconception_id])


class ReasoningError(Base):
    """Mapping of misconceptions to reasoning errors."""
    __tablename__ = "reasoning_errors"
    
    id = Column(Integer, primary_key=True)
    misconception_id = Column(Integer, ForeignKey("misconceptions.id"), nullable=False)
    error_type = Column(Enum(ReasoningErrorType), nullable=False)
    
    # Relationships
    misconception = relationship("Misconception", back_populates="reasoning_errors")


# ============================================================================
# SUBSCRIPTIONS & BILLING
# ============================================================================

class SubscriptionPlan(str, PyEnum):
    FREE = "free"
    PRO_MONTHLY = "pro_monthly"
    PRO_ANNUAL = "pro_annual"
    CLASSROOM = "classroom"
    INSTITUTION = "institution"


class SubscriptionStatus(str, PyEnum):
    FREE = "free"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELING = "canceling"
    CANCELED = "canceled"
    EXPIRED = "expired"


class Subscription(Base):
    """User subscription details."""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Plan
    plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE, nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.FREE, nullable=False)
    
    # Billing
    stripe_customer_id = Column(String(100), unique=True, index=True)
    stripe_subscription_id = Column(String(100), unique=True, index=True)
    
    # Dates
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    billing_cycle_anchor = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    
    # Auto-renewal
    auto_renew = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", uselist=False, back_populates="subscription")


class SubscriptionPrice(Base):
    """Pricing configuration for subscription plans."""
    __tablename__ = "subscription_prices"
    
    id = Column(Integer, primary_key=True)
    plan = Column(Enum(SubscriptionPlan), nullable=False)
    currency = Column(String(3), default="USD")
    amount_cents = Column(Integer, nullable=False)  # Amount in cents
    billing_period = Column(String(50))  # monthly, annual
    stripe_price_id = Column(String(100), unique=True, index=True)
    
    is_active = Column(Boolean, default=True)
    discount_percent = Column(Float, default=0.0)  # For annual vs monthly
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PaymentTransaction(Base):
    """Payment transaction records."""
    __tablename__ = "payment_transactions"
    
    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    stripe_payment_intent_id = Column(String(100), unique=True, index=True)
    
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(String(50))  # succeeded, processing, requires_action, requires_payment_method, canceled
    
    payment_method = Column(String(100))
    receipt_url = Column(String(512))
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class BillingEvent(Base):
    """Raw billing events from payment provider."""
    __tablename__ = "billing_events"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_type = Column(String(100), nullable=False)  # checkout.session.completed, invoice.payment_succeeded, etc.
    provider = Column(String(50), default="stripe")  # payment provider
    provider_event_id = Column(String(255), unique=True, index=True, nullable=False)
    
    payload = Column(JSON)  # Raw event data
    processed = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)


class Refund(Base):
    """Refund records."""
    __tablename__ = "refunds"
    
    id = Column(Integer, primary_key=True)
    payment_transaction_id = Column(Integer, ForeignKey("payment_transactions.id"), nullable=False)
    stripe_refund_id = Column(String(100), unique=True, index=True)
    
    amount_cents = Column(Integer, nullable=False)
    reason = Column(String(200))
    status = Column(String(50))  # succeeded, pending
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)


# ============================================================================
# ENTITLEMENTS & USAGE QUOTAS
# ============================================================================

class SubscriptionEntitlement(Base):
    """Features and limits for each subscription plan."""
    __tablename__ = "subscription_entitlements"
    
    id = Column(Integer, primary_key=True)
    plan = Column(Enum(SubscriptionPlan), nullable=False)
    feature_key = Column(String(100), nullable=False)  # e.g., 'unlimited_practice', 'circuit_lab'
    
    # Configuration
    is_enabled = Column(Boolean, default=True)
    config = Column(JSON)  # Feature-specific configuration
    
    __table_args__ = (
        UniqueConstraint("plan", "feature_key", name="uq_plan_feature"),
    )


class UsageQuota(Base):
    """Daily/monthly usage quotas for Free users."""
    __tablename__ = "usage_quotas"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Daily limits
    daily_problems_limit = Column(Integer, default=25)
    daily_problems_used = Column(Integer, default=0)
    daily_reset_at = Column(DateTime, nullable=True)
    
    # Monthly limits (if applicable)
    monthly_problems_limit = Column(Integer, default=200)
    monthly_problems_used = Column(Integer, default=0)
    monthly_reset_at = Column(DateTime, nullable=True)
    
    # Last reset
    last_reset_at = Column(DateTime, nullable=True)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", uselist=False, back_populates="usage_quota")


class UsageLedger(Base):
    """Detailed usage logging for quota tracking and debugging."""
    __tablename__ = "usage_ledger"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    feature_key = Column(String(100), nullable=False)
    usage_type = Column(String(50), nullable=False)  # consumed, refunded
    quantity = Column(Integer, default=1)
    
    # Reference
    problem_submission_id = Column(Integer, ForeignKey("problem_submissions.id"), nullable=True)
    idempotency_key = Column(String(255), unique=True, index=True)  # Prevent duplicate charges
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


# ============================================================================
# HELPER TABLES (Many-to-Many)
# ============================================================================

# Many-to-many: Question <-> Concept
question_concepts = Table(
    'question_concepts',
    Base.metadata,
    Column('question_id', Integer, ForeignKey('questions.id'), primary_key=True),
    Column('concept_id', Integer, ForeignKey('concept_tags.id'), primary_key=True)
)

# Many-to-many: Quiz <-> Question
quiz_questions = Table(
    'quiz_questions',
    Base.metadata,
    Column('quiz_id', Integer, ForeignKey('quizzes.id'), primary_key=True),
    Column('question_id', Integer, ForeignKey('questions.id'), primary_key=True),
    Column('order', Integer, default=0)
)

# Many-to-many: LearningPath <-> Course
learning_path_courses = Table(
    'learning_path_courses',
    Base.metadata,
    Column('learning_path_id', Integer, ForeignKey('learning_paths.id'), primary_key=True),
    Column('course_id', Integer, ForeignKey('courses.id'), primary_key=True),
    Column('order', Integer, default=0)
)

# Many-to-many: LearningPath prerequisites
learning_path_prerequisites = Table(
    'learning_path_prerequisites',
    Base.metadata,
    Column('learning_path_id', Integer, ForeignKey('learning_paths.id'), primary_key=True),
    Column('prerequisite_id', Integer, ForeignKey('learning_paths.id'), primary_key=True)
)

# Add relationships for many-to-many
Question.quizzes = relationship("Quiz", secondary="quiz_questions", back_populates="questions")
