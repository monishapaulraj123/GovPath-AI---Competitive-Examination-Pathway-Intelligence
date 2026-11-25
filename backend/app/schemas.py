from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class UserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=4, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=120)
    primary_target_exam: str = Field(default="UPSC_CSE")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Please provide a valid email address")
        return v


class UserLoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=2, max_length=120)
    age_range: Optional[str] = None
    educational_qualification: Optional[str] = None
    degree_discipline: Optional[str] = None
    graduation_status: Optional[str] = None
    state: Optional[str] = None
    preferred_language: Optional[str] = None
    current_occupation: Optional[str] = None
    aspirant_category: Optional[str] = None
    daily_study_hours: Optional[float] = Field(None, ge=0.5, le=16.0)
    days_per_week: Optional[int] = Field(None, ge=1, le=7)
    timeline_months: Optional[int] = Field(None, ge=1, le=60)
    previous_attempts: Optional[int] = Field(None, ge=0, le=20)
    previous_experience: Optional[str] = None
    preferred_job_categories: Optional[list[str]] = None
    career_preferences: Optional[str] = None
    preferred_exams: Optional[list[str]] = None
    primary_target_exam: Optional[str] = None
    secondary_target_exams: Optional[list[str]] = None
    constraints: Optional[str] = None
    ai_preferences: Optional[dict[str, Any]] = None
    notification_preferences: Optional[dict[str, Any]] = None
    privacy_preferences: Optional[dict[str, Any]] = None


class StartAssessmentRequest(BaseModel):
    exam_id: str
    assessment_type: str = Field(default="topic_quiz")
    subject_id: Optional[str] = None
    competency_id: Optional[str] = None
    question_count: int = Field(default=10, ge=3, le=50)
    time_limit_sec: Optional[int] = Field(default=None, ge=60, le=10800)


class AnswerSubmissionItem(BaseModel):
    question_id: str
    selected_index: Optional[int] = Field(None, ge=0, le=3)
    marked_for_review: bool = False
    time_spent_sec: int = Field(default=45, ge=1, le=3600)
    confidence_level: str = Field(default="medium")


class SubmitAssessmentRequest(BaseModel):
    answers: list[AnswerSubmissionItem]
    total_time_sec: int = Field(..., ge=1)


class StudyPlanGenerateRequest(BaseModel):
    exam_id: Optional[str] = None
    daily_hours: Optional[float] = Field(None, ge=0.5, le=16.0)
    days_per_week: Optional[int] = Field(None, ge=1, le=7)
    confirm_replace: bool = False
    focus_subjects: Optional[list[str]] = None


class StudyTaskCreateRequest(BaseModel):
    scheduled_date: str
    title: str = Field(..., min_length=2, max_length=180)
    subject_name: str
    topic_name: str
    competency_id: Optional[str] = None
    task_type: str = "concept_study"
    duration_minutes: int = Field(default=60, ge=10, le=480)
    priority: str = "medium"
    notes: str = ""


class StudyTaskUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=180)
    scheduled_date: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=10, le=480)
    priority: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class SimulatorRequest(BaseModel):
    target_exam_id: str
    daily_hours: float = Field(..., ge=0.5, le=16.0)
    days_per_week: int = Field(default=6, ge=1, le=7)
    duration_months: int = Field(..., ge=1, le=48)
    source_exam_id: Optional[str] = None
    focus_subject_ids: list[str] = Field(default_factory=list)
    subject_allocation_override: dict[str, float] = Field(default_factory=dict)


class CounsellorChatRequest(BaseModel):
    session_id: Optional[int] = None
    message: str = Field(..., min_length=1, max_length=4000)


class ApplyAgentProposalRequest(BaseModel):
    proposal_type: str
    payload: dict[str, Any]


class RAGDocumentIngestRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=220)
    exam_id: Optional[str] = None
    doc_type: str = Field(default="Curated Educational Resource")
    source_name: str = Field(..., min_length=2, max_length=180)
    source_url: str = ""
    verified_status: str = Field(default="User Ingested - Verify Against Official Portal")
    content: str = Field(..., min_length=30)


class SaveQuestionRequest(BaseModel):
    question_id: str
    note: str = ""
