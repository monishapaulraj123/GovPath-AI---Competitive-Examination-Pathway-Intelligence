from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.engines.planner import (
    build_adaptive_study_plan,
    generate_pathway_recommendations,
    serialize_study_plan,
)
from app.engines.simulator import run_what_if_simulation
from app.models import StudentProfile, StudyPlan, StudyTask, User
from app.schemas import (
    SimulatorRequest,
    StudyPlanGenerateRequest,
    StudyTaskCreateRequest,
    StudyTaskUpdateRequest,
)
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["Pathways, Study Plan & Simulator"])


@router.get("/pathways")
def get_pathways(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return generate_pathway_recommendations(db, current_user.id)


@router.get("/study-plan")
def get_active_study_plan(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = (
        db.query(StudyPlan)
        .filter(StudyPlan.user_id == current_user.id, StudyPlan.is_active == True)
        .order_by(StudyPlan.created_at.desc())
        .first()
    )
    if not plan:
        return {"has_plan": False, "plan": None}
    return {"has_plan": True, "plan": serialize_study_plan(plan)}


@router.post("/study-plan/generate")
def generate_study_plan(
    payload: StudyPlanGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(StudyPlan)
        .filter(StudyPlan.user_id == current_user.id, StudyPlan.is_active == True)
        .first()
    )
    if existing and not payload.confirm_replace:
        preview = build_adaptive_study_plan(
            db,
            current_user.id,
            exam_id=payload.exam_id,
            daily_hours=payload.daily_hours,
            days_per_week=payload.days_per_week,
            focus_subjects=payload.focus_subjects,
            persist=False,
        )
        return {
            "requires_confirmation": True,
            "message": "An active study plan already exists. Confirm replacement to activate the newly generated plan.",
            "preview_plan": preview,
        }

    plan = build_adaptive_study_plan(
        db,
        current_user.id,
        exam_id=payload.exam_id,
        daily_hours=payload.daily_hours,
        days_per_week=payload.days_per_week,
        focus_subjects=payload.focus_subjects,
        persist=True,
    )
    return {"requires_confirmation": False, "plan": plan}


@router.post("/study-plan/tasks")
def add_study_task(
    payload: StudyTaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = (
        db.query(StudyPlan)
        .filter(StudyPlan.user_id == current_user.id, StudyPlan.is_active == True)
        .first()
    )
    if not plan:
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
        plan = StudyPlan(
            user_id=current_user.id,
            exam_id=profile.primary_target_exam if profile else "UPSC_CSE",
            title="Custom Study Plan",
            daily_hours=profile.daily_study_hours if profile else 4.0,
            days_per_week=profile.days_per_week if profile else 6,
            is_active=True,
            generation_rationale="User-created custom study tasks.",
        )
        db.add(plan)
        db.flush()

    task = StudyTask(
        plan_id=plan.id,
        user_id=current_user.id,
        day_index=1,
        scheduled_date=payload.scheduled_date,
        title=payload.title,
        subject_name=payload.subject_name,
        topic_name=payload.topic_name,
        competency_id=payload.competency_id,
        task_type=payload.task_type,
        duration_minutes=payload.duration_minutes,
        priority=payload.priority,
        notes=payload.notes,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(plan)
    return serialize_study_plan(plan)


@router.patch("/study-plan/tasks/{task_id}")
def update_study_task(
    task_id: int,
    payload: StudyTaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(StudyTask)
        .filter(StudyTask.id == task_id, StudyTask.user_id == current_user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Study task not found")

    data = payload.model_dump(exclude_unset=True)
    for key, val in data.items():
        setattr(task, key, val)
    if data.get("status") == "completed":
        task.completed_at = datetime.now(timezone.utc)
    elif data.get("status") in ("pending", "skipped"):
        task.completed_at = None

    db.commit()
    plan = db.query(StudyPlan).filter(StudyPlan.id == task.plan_id).first()
    return serialize_study_plan(plan)


@router.delete("/study-plan/tasks/{task_id}")
def delete_study_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(StudyTask)
        .filter(StudyTask.id == task_id, StudyTask.user_id == current_user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Study task not found")
    plan_id = task.plan_id
    db.delete(task)
    db.commit()
    plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id).first()
    return serialize_study_plan(plan)


@router.post("/simulator")
def simulate_scenario(
    payload: SimulatorRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return run_what_if_simulation(
        db=db,
        user_id=current_user.id,
        target_exam_id=payload.target_exam_id,
        daily_hours=payload.daily_hours,
        days_per_week=payload.days_per_week,
        duration_months=payload.duration_months,
        source_exam_id=payload.source_exam_id,
        focus_subject_ids=payload.focus_subject_ids,
    )
