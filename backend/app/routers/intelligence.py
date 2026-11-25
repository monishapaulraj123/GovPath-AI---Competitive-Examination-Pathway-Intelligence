from collections import defaultdict
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.engines.diagnosis import compute_performance_diagnosis
from app.engines.gap_analysis import compute_gap_analysis
from app.engines.readiness import compute_readiness_profile
from app.engines.retention import compute_retention_tracker
from app.engines.transfer import analyze_knowledge_transfer
from app.models import AssessmentAttempt, CompetencyEvidence, StudentProfile, StudyTask, User
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["Intelligence & Analytics"])


def _resolve_exam_id(db: Session, user_id: int, exam_id: Optional[str]) -> str:
    if exam_id:
        return exam_id
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    return profile.primary_target_exam if profile else "UPSC_CSE"


@router.get("/readiness")
def get_readiness(
    exam_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _resolve_exam_id(db, current_user.id, exam_id)
    return compute_readiness_profile(db, current_user.id, target)


@router.get("/gap-analysis")
def get_gap_analysis(
    exam_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _resolve_exam_id(db, current_user.id, exam_id)
    return compute_gap_analysis(db, current_user.id, target)


@router.get("/knowledge-transfer")
def get_knowledge_transfer(
    source_exam_id: str = Query(default="UPSC_CSE"),
    target_exam_id: str = Query(default="TNPSC_GRP1"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return analyze_knowledge_transfer(db, current_user.id, source_exam_id, target_exam_id)


@router.get("/diagnosis")
def get_performance_diagnosis(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return compute_performance_diagnosis(db, current_user.id)


@router.get("/retention")
def get_retention_tracker(
    exam_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _resolve_exam_id(db, current_user.id, exam_id)
    return compute_retention_tracker(db, current_user.id, target)


@router.get("/analytics")
def get_performance_analytics(
    exam_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _resolve_exam_id(db, current_user.id, exam_id)
    readiness = compute_readiness_profile(db, current_user.id, target)
    diagnosis = compute_performance_diagnosis(db, current_user.id)

    attempts = (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.user_id == current_user.id, AssessmentAttempt.status == "completed")
        .order_by(AssessmentAttempt.completed_at.asc())
        .all()
    )
    if exam_id:
        filtered_attempts = [a for a in attempts if a.exam_id == exam_id]
        if filtered_attempts:
            attempts = filtered_attempts

    attempt_trends = [
        {
            "id": a.id,
            "date": a.completed_at.date().isoformat() if a.completed_at else "",
            "title": a.title,
            "exam_id": a.exam_id,
            "score_percent": a.score_percent,
            "accuracy_percent": a.accuracy_percent,
            "avg_time_per_q": round(a.time_taken_sec / max(1, a.total_questions), 1),
        }
        for a in attempts
    ]

    evidences = (
        db.query(CompetencyEvidence)
        .filter(CompetencyEvidence.user_id == current_user.id)
        .order_by(CompetencyEvidence.recorded_at.asc())
        .all()
    )
    daily_scores: dict[str, list[float]] = defaultdict(list)
    for ev in evidences:
        d = ev.recorded_at.date().isoformat() if ev.recorded_at else "unknown"
        daily_scores[d].append(ev.observed_score)

    competency_trend = [
        {"date": d, "avg_mastery": round(sum(vals) / len(vals), 1), "observations": len(vals)}
        for d, vals in sorted(daily_scores.items())
    ]

    tasks = db.query(StudyTask).filter(StudyTask.user_id == current_user.id).all()
    completed_mins = sum(t.duration_minutes for t in tasks if t.status == "completed")
    planned_mins = sum(t.duration_minutes for t in tasks)
    revision_tasks = [t for t in tasks if t.task_type == "revision"]
    revision_done = sum(1 for t in revision_tasks if t.status == "completed")

    subject_perf = readiness["subject_breakdown"]
    if subject_id and subject_id != "ALL":
        subject_perf = [s for s in subject_perf if s["subject_id"] == subject_id]

    return {
        "exam_id": target,
        "has_only_demo_data": readiness["has_only_demo_data"],
        "summary_kpis": {
            "readiness_index": readiness["readiness_index"],
            "accuracy": readiness["accuracy"],
            "consistency": readiness["consistency"],
            "retention_index": readiness["retention_index"],
            "completed_study_hours": round(completed_mins / 60.0, 1),
            "planned_study_hours": round(planned_mins / 60.0, 1),
            "revision_completion_percent": round((revision_done / max(1, len(revision_tasks))) * 100.0, 1) if revision_tasks else 0.0,
            "assessments_completed": len(attempts),
        },
        "attempt_trends": attempt_trends,
        "competency_trend": competency_trend,
        "subject_performance": subject_perf,
        "competency_details": [
            c for c in readiness["competencies"]
            if (not subject_id or subject_id == "ALL" or c["subject_id"] == subject_id) and c["evidence_count"] > 0
        ],
        "error_breakdown": diagnosis.get("error_category_breakdown", {}),
        "difficulty_performance": diagnosis.get("difficulty_performance", {}),
    }
