"""
AI Pathway Recommendation & Adaptive Study Plan Generator.
Combines profile constraints, readiness, gap priorities, knowledge transfer, and retention urgency.
"""

from datetime import date, timedelta
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.engines.gap_analysis import compute_gap_analysis
from app.engines.readiness import compute_readiness_profile
from app.engines.retention import compute_retention_tracker
from app.engines.transfer import analyze_knowledge_transfer
from app.models import Exam, StudentProfile, StudyPlan, StudyTask


def generate_pathway_recommendations(db: Session, user_id: int) -> dict[str, Any]:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    exams = db.query(Exam).all()
    primary_id = profile.primary_target_exam if profile else "UPSC_CSE"
    daily_hours = profile.daily_study_hours if profile else 4.5
    timeline_months = profile.timeline_months if profile else 12
    preferred_cats = set(profile.preferred_job_categories or []) if profile else set()
    state = (profile.state or "").lower() if profile else ""

    ranked: list[dict[str, Any]] = []
    for ex in exams:
        readiness = compute_readiness_profile(db, user_id, ex.id)
        gap_info = compute_gap_analysis(db, user_id, ex.id)
        transfer = analyze_knowledge_transfer(db, user_id, primary_id, ex.id) if ex.id != primary_id else None

        hours_fit = min(100.0, (daily_hours / max(1.0, ex.recommended_daily_hours)) * 100.0)
        pref_bonus = 8.0 if any(c.lower() in ex.category.lower() for c in preferred_cats) else 0.0
        state_bonus = 6.0 if ("tamil nadu" in state and "TNPSC" in ex.id) else 0.0
        transfer_score = transfer["effective_transfer_index"] if transfer else 100.0

        suitability_score = round(
            min(
                99.0,
                readiness["readiness_index"] * 0.35
                + transfer_score * 0.30
                + hours_fit * 0.25
                + pref_bonus
                + state_bonus,
            ),
            1,
        )

        role = "Alternative"
        if ex.id == primary_id:
            role = "Primary Target"
        elif profile and ex.id in (profile.secondary_target_exams or []):
            role = "Secondary Target"

        ranked.append({
            "exam_id": ex.id,
            "exam_name": ex.name,
            "short_name": ex.short_name,
            "category": ex.category,
            "role": role,
            "suitability_score": suitability_score,
            "readiness_index": readiness["readiness_index"],
            "overall_gap": gap_info["overall_weighted_gap"],
            "transfer_from_primary_percent": transfer_score,
            "estimated_additional_hours": transfer["estimated_additional_hours"] if transfer else round(gap_info["overall_weighted_gap"] * 4.5, 1),
            "recommended_daily_hours": ex.recommended_daily_hours,
            "hours_feasibility_percent": round(hours_fit, 1),
            "rationale": (
                f"Readiness {readiness['readiness_index']}% | "
                f"Overlap/Transfer {transfer_score}% from {primary_id} | "
                f"Daily time fit {round(hours_fit)}% for {daily_hours}h/day over {timeline_months} months."
            ),
        })

    # Assign suggested Primary / Secondary / Backup if user wants recommendations
    non_primary = sorted([r for r in ranked if r["exam_id"] != primary_id], key=lambda x: -x["suitability_score"])
    if non_primary:
        if non_primary[0]["role"] == "Alternative":
            non_primary[0]["role"] = "Recommended Secondary"
    if len(non_primary) >= 2 and non_primary[1]["role"] == "Alternative":
        non_primary[1]["role"] = "Recommended Backup"

    ranked.sort(key=lambda x: (0 if x["exam_id"] == primary_id else 1, -x["suitability_score"]))

    return {
        "primary_exam_id": primary_id,
        "student_constraints": {
            "daily_study_hours": daily_hours,
            "days_per_week": profile.days_per_week if profile else 6,
            "timeline_months": timeline_months,
            "state": profile.state if profile else "",
            "occupation": profile.current_occupation if profile else "",
        },
        "pathways": ranked,
    }


def build_adaptive_study_plan(
    db: Session,
    user_id: int,
    exam_id: Optional[str] = None,
    daily_hours: Optional[float] = None,
    days_per_week: Optional[int] = None,
    focus_subjects: Optional[list[str]] = None,
    persist: bool = True,
) -> dict[str, Any]:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    target_exam_id = exam_id or (profile.primary_target_exam if profile else "UPSC_CSE")
    eff_hours = daily_hours or (profile.daily_study_hours if profile else 4.5)
    eff_days = days_per_week or (profile.days_per_week if profile else 6)

    gap_data = compute_gap_analysis(db, user_id, target_exam_id)
    retention_data = compute_retention_tracker(db, user_id, target_exam_id)
    exam = db.query(Exam).filter(Exam.id == target_exam_id).first()

    gaps = gap_data["competency_gaps"]
    if focus_subjects:
        focused = [g for g in gaps if g["subject_id"] in focus_subjects]
        others = [g for g in gaps if g["subject_id"] not in focus_subjects]
        gaps = focused + others

    overdue_revisions = [
        r for r in retention_data["items"] if r["revision_status"] in ("Revision Overdue", "Due Soon")
    ]

    daily_minutes = int(round(eff_hours * 60))
    start_day = date.today()
    generated_tasks: list[dict[str, Any]] = []

    for d_idx in range(1, eff_days + 1):
        sched_date = (start_day + timedelta(days=d_idx - 1)).isoformat()
        rem_mins = daily_minutes

        # Slot 1: Highest priority gap concept/practice block
        if gaps:
            g = gaps[(d_idx - 1) % len(gaps)]
            block1_mins = min(rem_mins, max(45, int(daily_minutes * 0.45)))
            rem_mins -= block1_mins
            generated_tasks.append({
                "day_index": d_idx,
                "scheduled_date": sched_date,
                "title": f"Deep Study: {g['topic_name']} ({g['priority']} Gap)",
                "subject_name": g["subject_name"],
                "topic_name": g["topic_name"],
                "competency_id": g["competency_id"],
                "task_type": "concept_study",
                "duration_minutes": block1_mins,
                "priority": "high" if g["priority"] in ("Critical", "High") else "medium",
                "notes": g["recommended_intervention"],
            })

        # Slot 2: Secondary gap or practice quiz
        if rem_mins >= 30 and len(gaps) > 1:
            g2 = gaps[d_idx % len(gaps)]
            block2_mins = min(rem_mins, max(35, int(daily_minutes * 0.30)))
            rem_mins -= block2_mins
            generated_tasks.append({
                "day_index": d_idx,
                "scheduled_date": sched_date,
                "title": f"MCQ Drill: {g2['topic_name']}",
                "subject_name": g2["subject_name"],
                "topic_name": g2["topic_name"],
                "competency_id": g2["competency_id"],
                "task_type": "practice_quiz",
                "duration_minutes": block2_mins,
                "priority": "high" if g2["priority"] in ("Critical", "High") else "medium",
                "notes": f"Close {g2['gap']}-point gap against required depth {g2['required_level']}.",
            })

        # Slot 3: Spaced revision / mock review
        if rem_mins >= 25:
            if overdue_revisions:
                rev = overdue_revisions[(d_idx - 1) % len(overdue_revisions)]
                generated_tasks.append({
                    "day_index": d_idx,
                    "scheduled_date": sched_date,
                    "title": f"Retention Review: {rev['topic_name']}",
                    "subject_name": rev["subject_name"],
                    "topic_name": rev["topic_name"],
                    "competency_id": rev["competency_id"],
                    "task_type": "revision",
                    "duration_minutes": rem_mins,
                    "priority": "high" if rev["revision_status"] == "Revision Overdue" else "medium",
                    "notes": f"Status: {rev['revision_status']} (Last assessed: {rev['last_assessed_date'] or 'Not yet assessed'}).",
                })
            elif gaps:
                g3 = gaps[(d_idx + 1) % len(gaps)]
                generated_tasks.append({
                    "day_index": d_idx,
                    "scheduled_date": sched_date,
                    "title": f"Active Recall & Notes: {g3['topic_name']}",
                    "subject_name": g3["subject_name"],
                    "topic_name": g3["topic_name"],
                    "competency_id": g3["competency_id"],
                    "task_type": "revision",
                    "duration_minutes": rem_mins,
                    "priority": "medium",
                    "notes": "Consolidate high-yield facts and error log notes.",
                })

    rationale = (
        f"Adapted for {exam.short_name if exam else target_exam_id} at {eff_hours}h/day × {eff_days} days/week. "
        f"Prioritized {gap_data['priority_counts']['Critical'] + gap_data['priority_counts']['High']} high/critical gaps "
        f"and {len(overdue_revisions)} due revision topics."
    )

    if not persist:
        return {
            "exam_id": target_exam_id,
            "daily_hours": eff_hours,
            "days_per_week": eff_days,
            "generation_rationale": rationale,
            "tasks": generated_tasks,
        }

    # Deactivate existing active plans
    db.query(StudyPlan).filter(StudyPlan.user_id == user_id, StudyPlan.is_active == True).update({"is_active": False})

    plan = StudyPlan(
        user_id=user_id,
        exam_id=target_exam_id,
        title=f"{exam.short_name if exam else target_exam_id} Adaptive Weekly Plan",
        daily_hours=eff_hours,
        days_per_week=eff_days,
        is_active=True,
        generation_rationale=rationale,
    )
    db.add(plan)
    db.flush()

    for t in generated_tasks:
        db.add(StudyTask(plan_id=plan.id, user_id=user_id, **t))

    db.commit()
    db.refresh(plan)
    return serialize_study_plan(plan)


def serialize_study_plan(plan: StudyPlan) -> dict[str, Any]:
    tasks = sorted(plan.tasks, key=lambda t: (t.day_index, t.id))
    completed = sum(1 for t in tasks if t.status == "completed")
    skipped = sum(1 for t in tasks if t.status == "skipped")
    total_mins = sum(t.duration_minutes for t in tasks)
    done_mins = sum(t.duration_minutes for t in tasks if t.status == "completed")

    return {
        "id": plan.id,
        "exam_id": plan.exam_id,
        "title": plan.title,
        "daily_hours": plan.daily_hours,
        "days_per_week": plan.days_per_week,
        "is_active": plan.is_active,
        "generation_rationale": plan.generation_rationale,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "progress": {
            "total_tasks": len(tasks),
            "completed_tasks": completed,
            "skipped_tasks": skipped,
            "pending_tasks": len(tasks) - completed - skipped,
            "completion_percent": round((completed / max(1, len(tasks))) * 100.0, 1),
            "planned_hours": round(total_mins / 60.0, 1),
            "completed_hours": round(done_mins / 60.0, 1),
        },
        "tasks": [
            {
                "id": t.id,
                "plan_id": t.plan_id,
                "day_index": t.day_index,
                "scheduled_date": t.scheduled_date,
                "title": t.title,
                "subject_name": t.subject_name,
                "topic_name": t.topic_name,
                "competency_id": t.competency_id,
                "task_type": t.task_type,
                "duration_minutes": t.duration_minutes,
                "priority": t.priority,
                "status": t.status,
                "notes": t.notes,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ],
    }
