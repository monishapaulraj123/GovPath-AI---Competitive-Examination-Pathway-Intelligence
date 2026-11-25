from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=False)
    is_demo = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    profile = relationship("StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    display_name = Column(String(120), nullable=False)
    age_range = Column(String(40), default="21-25")
    educational_qualification = Column(String(120), default="Bachelor's Degree")
    degree_discipline = Column(String(120), default="Engineering / Technology")
    graduation_status = Column(String(60), default="Completed")
    state = Column(String(80), default="Tamil Nadu")
    preferred_language = Column(String(60), default="English")
    current_occupation = Column(String(80), default="Graduate / Full-time Aspirant")
    aspirant_category = Column(String(60), default="graduate")
    daily_study_hours = Column(Float, default=4.5)
    days_per_week = Column(Integer, default=6)
    timeline_months = Column(Integer, default=12)
    previous_attempts = Column(Integer, default=0)
    previous_experience = Column(Text, default="")
    preferred_job_categories = Column(JSON, default=list)
    career_preferences = Column(Text, default="")
    preferred_exams = Column(JSON, default=list)
    primary_target_exam = Column(String(60), default="UPSC_CSE")
    secondary_target_exams = Column(JSON, default=lambda: ["TNPSC_GRP1", "SSC_CGL"])
    constraints = Column(Text, default="")
    ai_preferences = Column(JSON, default=lambda: {"explanation_depth": "balanced", "socratic_hints": True, "auto_suggest_plan_updates": True})
    notification_preferences = Column(JSON, default=lambda: {"revision_reminders": True, "plan_alerts": True, "exam_updates": True, "weekly_digest": True})
    privacy_preferences = Column(JSON, default=lambda: {"share_anonymized_metrics": False, "retain_chat_history": True})
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="profile")


class Exam(Base):
    __tablename__ = "exams"

    id = Column(String(60), primary_key=True, index=True)
    name = Column(String(180), nullable=False)
    short_name = Column(String(60), nullable=False)
    category = Column(String(60), nullable=False)
    conducting_authority = Column(String(180), nullable=False)
    overview = Column(Text, nullable=False)
    eligibility_summary = Column(Text, nullable=False)
    verification_note = Column(Text, nullable=False)
    official_sources = Column(JSON, default=list)
    stages = Column(JSON, default=list)
    exam_pattern = Column(JSON, default=list)
    preparation_resources = Column(JSON, default=list)
    difficulty_index = Column(Float, default=75.0)
    recommended_daily_hours = Column(Float, default=5.0)


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(String(60), primary_key=True)
    name = Column(String(120), nullable=False)
    domain = Column(String(80), nullable=False)
    description = Column(Text, default="")


class Competency(Base):
    __tablename__ = "competencies"

    id = Column(String(80), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    subject_id = Column(String(60), ForeignKey("subjects.id"), nullable=False)
    topic_name = Column(String(150), nullable=False)
    subtopics = Column(JSON, default=list)
    description = Column(Text, default="")
    prerequisites = Column(JSON, default=list)
    base_learning_hours = Column(Float, default=14.0)


class ExamCompetencyRequirement(Base):
    __tablename__ = "exam_competency_requirements"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(String(60), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    competency_id = Column(String(80), ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False, index=True)
    required_depth = Column(Float, nullable=False)  # 0-100 scale
    weightage_percent = Column(Float, default=5.0)
    exam_subject_label = Column(String(120), nullable=False)
    stage_relevance = Column(String(120), default="Prelims & Mains")


class Question(Base):
    __tablename__ = "questions"

    id = Column(String(80), primary_key=True, index=True)
    prompt = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # list of 4 strings
    correct_index = Column(Integer, nullable=False)
    explanation = Column(Text, nullable=False)
    subject_id = Column(String(60), ForeignKey("subjects.id"), nullable=False)
    topic_name = Column(String(150), nullable=False)
    competency_id = Column(String(80), ForeignKey("competencies.id"), nullable=False, index=True)
    difficulty = Column(String(30), default="medium")  # easy, medium, hard
    exam_mappings = Column(JSON, default=list)
    expected_time_sec = Column(Integer, default=60)
    source_type = Column(String(60), default="Curated Demo Question")
    source_label = Column(String(180), default="GovPath Academic Curated Bank")


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exam_id = Column(String(60), ForeignKey("exams.id"), nullable=False)
    assessment_type = Column(String(40), nullable=False)  # diagnostic, topic_quiz, subject_test, mock_test, revision
    title = Column(String(180), nullable=False)
    question_ids = Column(JSON, default=list)
    status = Column(String(30), default="in_progress")  # in_progress, completed
    score_percent = Column(Float, default=0.0)
    accuracy_percent = Column(Float, default=0.0)
    total_questions = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)
    unanswered_count = Column(Integer, default=0)
    time_limit_sec = Column(Integer, default=900)
    time_taken_sec = Column(Integer, default=0)
    is_demo_seed = Column(Boolean, default=False)
    started_at = Column(DateTime(timezone=True), default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(String(80), ForeignKey("questions.id"), nullable=False)
    competency_id = Column(String(80), ForeignKey("competencies.id"), nullable=False)
    selected_index = Column(Integer, nullable=True)
    is_correct = Column(Boolean, default=False)
    marked_for_review = Column(Boolean, default=False)
    time_spent_sec = Column(Integer, default=45)
    confidence_level = Column(String(20), default="medium")
    error_category = Column(String(60), nullable=True)


class CompetencyEvidence(Base):
    __tablename__ = "competency_evidence"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    competency_id = Column(String(80), ForeignKey("competencies.id"), nullable=False, index=True)
    source_type = Column(String(40), nullable=False)  # diagnostic, mock_test, topic_quiz, revision, study_task
    attempt_id = Column(Integer, nullable=True)
    observed_score = Column(Float, nullable=False)  # 0-100
    accuracy = Column(Float, nullable=False)
    speed_efficiency = Column(Float, default=80.0)
    weight = Column(Float, default=1.0)
    is_demo_seed = Column(Boolean, default=False)
    recorded_at = Column(DateTime(timezone=True), default=utcnow)


class SavedQuestion(Base):
    __tablename__ = "saved_questions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(String(80), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exam_id = Column(String(60), ForeignKey("exams.id"), nullable=False)
    title = Column(String(180), nullable=False)
    daily_hours = Column(Float, default=4.5)
    days_per_week = Column(Integer, default=6)
    is_active = Column(Boolean, default=True)
    generation_rationale = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)

    tasks = relationship("StudyTask", back_populates="plan", cascade="all, delete-orphan")


class StudyTask(Base):
    __tablename__ = "study_tasks"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    day_index = Column(Integer, default=1)  # 1..7 for weekly cycle
    scheduled_date = Column(String(20), nullable=False)  # YYYY-MM-DD
    title = Column(String(180), nullable=False)
    subject_name = Column(String(120), nullable=False)
    topic_name = Column(String(150), nullable=False)
    competency_id = Column(String(80), nullable=True)
    task_type = Column(String(40), default="concept_study")  # concept_study, revision, practice_quiz, mock_review
    duration_minutes = Column(Integer, default=60)
    priority = Column(String(20), default="high")
    status = Column(String(20), default="pending")  # pending, completed, skipped
    notes = Column(Text, default="")
    completed_at = Column(DateTime(timezone=True), nullable=True)

    plan = relationship("StudyPlan", back_populates="tasks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(180), default="New Counselling Session")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    citations = Column(JSON, default=list)
    agent_trace = Column(JSON, default=list)
    proposed_action = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    session = relationship("ChatSession", back_populates="messages")


class RAGDocument(Base):
    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(220), nullable=False)
    exam_id = Column(String(60), nullable=True, index=True)
    doc_type = Column(String(60), default="Official Syllabus")
    source_name = Column(String(180), nullable=False)
    source_url = Column(String(300), default="")
    verified_status = Column(String(60), default="Verified Reference")
    raw_text = Column(Text, nullable=False)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class RAGChunk(Base):
    __tablename__ = "rag_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    chunk_metadata = Column(JSON, default=dict)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    message = Column(Text, nullable=False)
    category = Column(String(40), default="insight")  # revision, study_plan, assessment, insight, exam_info
    action_route = Column(String(120), default="/")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
