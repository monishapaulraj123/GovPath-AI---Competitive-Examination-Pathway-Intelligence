from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.engines.gap_analysis import compute_gap_analysis
from app.engines.planner import generate_pathway_recommendations, serialize_study_plan
from app.engines.readiness import compute_readiness_profile
from app.engines.retention import compute_retention_tracker
from app.models import Notification, StudentProfile, StudyPlan, User
from app.schemas import ProfileUpdateRequest
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["Profile & Dashboard"])


def _serialize_profile(p: StudentProfile, user: User) -> dict:
    return {
        "user_id": p.user_id,
        "email": user.email,
        "is_demo": user.is_demo,
        "display_name": p.display_name,
        "age_range": p.age_range,
        "educational_qualification": p.educational_qualification,
        "degree_discipline": p.degree_discipline,
        "graduation_status": p.graduation_status,
        "state": p.state,
        "preferred_language": p.preferred_language,
        "current_occupation": p.current_occupation,
        "aspirant_category": p.aspirant_category,
        "daily_study_hours": p.daily_study_hours,
        "days_per_week": p.days_per_week,
        "timeline_months": p.timeline_months,
        "previous_attempts": p.previous_attempts,
        "previous_experience": p.previous_experience,
        "preferred_job_categories": p.preferred_job_categories or [],
        "career_preferences": p.career_preferences,
        "preferred_exams": p.preferred_exams or [],
        "primary_target_exam": p.primary_target_exam,
        "secondary_target_exams": p.secondary_target_exams or [],
        "constraints": p.constraints,
        "ai_preferences": p.ai_preferences or {},
        "notification_preferences": p.notification_preferences or {},
        "privacy_preferences": p.privacy_preferences or {},
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/profile")
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        profile = StudentProfile(user_id=current_user.id, display_name=current_user.full_name)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return _serialize_profile(profile, current_user)


@router.put("/profile")
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        profile = StudentProfile(user_id=current_user.id, display_name=current_user.full_name)
        db.add(profile)

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(profile, key, value)
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return _serialize_profile(profile, current_user)


@router.get("/dashboard")
def get_dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    primary_exam = profile.primary_target_exam if profile else "UPSC_CSE"

    readiness = compute_readiness_profile(db, current_user.id, primary_exam)
    gaps = compute_gap_analysis(db, current_user.id, primary_exam)
    retention = compute_retention_tracker(db, current_user.id, primary_exam)
    pathways = generate_pathway_recommendations(db, current_user.id)

    active_plan = (
        db.query(StudyPlan)
        .filter(StudyPlan.user_id == current_user.id, StudyPlan.is_active == True)
        .order_by(StudyPlan.created_at.desc())
        .first()
    )
    plan_data = serialize_study_plan(active_plan) if active_plan else None
    today_tasks = [t for t in (plan_data["tasks"] if plan_data else []) if t["day_index"] == 1]

    # Data-driven AI insights generated directly from computed readiness/gaps/retention/transfer
    insights: list[dict] = []
    if readiness["assessments_completed"] == 0:
        insights.append({
            "type": "action",
            "title": "Establish Your Competency Baseline",
            "detail": "No assessments completed yet. Run a 10-question diagnostic so Readiness & Gap engines calibrate to your real skill profile.",
            "route": "/assessments",
        })
    else:
        if gaps["top_priorities"]:
            top_g = gaps["top_priorities"][0]
            insights.append({
                "type": "gap",
                "title": f"{top_g['subject_name']} shows a {top_g['priority']} gap ({top_g['gap']} pts)",
                "detail": top_g["recommended_intervention"],
                "route": "/gap-analysis",
            })
        overdue = [r for r in retention["items"] if r["revision_status"] in ("Revision Overdue", "Due Soon")]
        if overdue:
            insights.append({
                "type": "retention",
                "title": f"{len(overdue)} competencies due for spaced retrieval",
                "detail": f"Highest urgency: {overdue[0]['topic_name']} ({overdue[0]['revision_status']}).",
                "route": "/retention",
            })
        if len(pathways["pathways"]) > 1:
            sec = pathways["pathways"][1]
            insights.append({
                "type": "transfer",
                "title": f"{sec['transfer_from_primary_percent']}% transfer alignment to {sec['short_name']}",
                "detail": f"Estimated ~{sec['estimated_additional_hours']} bridge hours to unlock {sec['short_name']} as a parallel track.",
                "route": "/knowledge-transfer",
            })
        if plan_data and plan_data["progress"]["completion_percent"] < 40:
            insights.append({
                "type": "plan",
                "title": "Study schedule execution needs momentum",
                "detail": f"{plan_data['progress']['completed_tasks']} of {plan_data['progress']['total_tasks']} planned tasks completed this cycle.",
                "route": "/study-plan",
            })

    unread_notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read == False)
        .count()
    )

    return {
        "profile": _serialize_profile(profile, current_user) if profile else None,
        "readiness": {
            "exam_id": readiness["exam_id"],
            "exam_name": readiness["exam_name"],
            "exam_short_name": readiness["exam_short_name"],
            "readiness_index": readiness["readiness_index"],
            "competency_coverage": readiness["competency_coverage"],
            "retention_index": readiness["retention_index"],
            "accuracy": readiness["accuracy"],
            "consistency": readiness["consistency"],
            "assessments_completed": readiness["assessments_completed"],
            "has_only_demo_data": readiness["has_only_demo_data"],
            "subject_breakdown": readiness["subject_breakdown"],
        },
        "gap_overview": gaps["subject_gaps"][:6],
        "top_competency_gaps": gaps["top_priorities"][:5],
        "study_activity": {
            "has_active_plan": plan_data is not None,
            "plan_title": plan_data["title"] if plan_data else None,
            "progress": plan_data["progress"] if plan_data else None,
            "today_tasks": today_tasks,
        },
        "insights": insights,
        "pathway_overview": pathways["pathways"][:4],
        "unread_notifications": unread_notifications,
    }


@router.get("/notifications")
def list_notifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return {
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "category": n.category,
                "action_route": n.action_route,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in items
        ]
    }


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
def mark_all_notifications_read(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.user_id == current_user.id).update({"is_read": True})
    db.commit()
    return {"ok": True}
