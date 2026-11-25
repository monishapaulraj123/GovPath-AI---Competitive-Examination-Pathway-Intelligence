"""
Transparent What-If Scenario Simulator.
Models estimated competency coverage, gap reduction, and workload across target/hour/duration scenarios.
"""

from typing import Any, Optional
from sqlalchemy.orm import Session
from app.engines.gap_analysis import compute_gap_analysis
from app.engines.transfer import HOURS_PER_GAP_POINT_FACTOR, analyze_knowledge_transfer
from app.models import Exam, StudentProfile


def run_what_if_simulation(
    db: Session,
    user_id: int,
    target_exam_id: str,
    daily_hours: float,
    days_per_week: int,
    duration_months: int,
    source_exam_id: Optional[str] = None,
    focus_subject_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    baseline_exam_id = source_exam_id or (profile.primary_target_exam if profile else "UPSC_CSE")
    baseline_hours = profile.daily_study_hours if profile else 4.5
    baseline_days = profile.days_per_week if profile else 6
    baseline_months = profile.timeline_months if profile else 12

    target_exam = db.query(Exam).filter(Exam.id == target_exam_id).first()
    gap_data = compute_gap_analysis(db, user_id, target_exam_id)
    transfer_data = (
        analyze_knowledge_transfer(db, user_id, baseline_exam_id, target_exam_id)
        if baseline_exam_id != target_exam_id
        else None
    )

    total_available_hours = round(daily_hours * days_per_week * 4.33 * duration_months, 1)
    baseline_available_hours = round(baseline_hours * baseline_days * 4.33 * baseline_months, 1)

    # Effective learning hours (accounting for ~25% revision/mock testing allocation)
    effective_gap_closing_hours = total_available_hours * 0.75
    baseline_effective_hours = baseline_available_hours * 0.75

    # Calculate required hours to close remaining gap
    total_gap_points = sum(g["gap"] * (g["weightage_percent"] / 100.0) for g in gap_data["competency_gaps"])
    required_hours_est = round(
        sum(g["gap"] * HOURS_PER_GAP_POINT_FACTOR for g in gap_data["competency_gaps"]), 1
    )

    # Diminishing returns saturation curve for projected readiness alignment
    focus_set = set(focus_subject_ids or [])
    projected_competencies = []
    projected_weight_sum = 0.0
    projected_align_sum = 0.0
    projected_gap_sum = 0.0

    # Distribute effective hours across competencies weighted by gap and focus multiplier
    raw_needs = []
    for g in gap_data["competency_gaps"]:
        mult = 1.45 if g["subject_id"] in focus_set else 1.0
        raw_needs.append(max(0.1, g["gap"] * mult * (g["weightage_percent"] / 10.0)))
    total_need = max(1.0, sum(raw_needs))

    for g, need in zip(gap_data["competency_gaps"], raw_needs):
        allocated_hrs = effective_gap_closing_hours * (need / total_need)
        potential_gain = allocated_hrs / HOURS_PER_GAP_POINT_FACTOR
        # Cap at realistic ceiling of 96 mastery
        projected_score = round(min(96.0, g["current_evidence"] + min(g["gap"], potential_gain * 0.85)), 1)
        new_gap = round(max(0.0, g["required_level"] - projected_score), 1)
        align = min(100.0, (projected_score / max(1.0, g["required_level"])) * 100.0)

        projected_align_sum += align * g["weightage_percent"]
        projected_gap_sum += new_gap * g["weightage_percent"]
        projected_weight_sum += g["weightage_percent"]

        projected_competencies.append({
            "competency_id": g["competency_id"],
            "competency_name": g["competency_name"],
            "subject_id": g["subject_id"],
            "current_mastery": g["current_evidence"],
            "projected_mastery": projected_score,
            "required_depth": g["required_level"],
            "current_gap": g["gap"],
            "projected_gap": new_gap,
            "allocated_study_hours": round(allocated_hrs, 1),
        })

    projected_readiness = round(projected_align_sum / max(1.0, projected_weight_sum), 1)
    projected_gap = round(projected_gap_sum / max(1.0, projected_weight_sum), 1)

    workload_ratio = round(total_available_hours / max(1.0, required_hours_est), 2)
    feasibility_status = (
        "Comfortable Cushion" if workload_ratio >= 1.35 else ("Feasible" if workload_ratio >= 0.95 else "Time-Constrained")
    )

    return {
        "scenario": {
            "target_exam_id": target_exam_id,
            "target_exam_name": target_exam.short_name if target_exam else target_exam_id,
            "source_exam_id": baseline_exam_id,
            "daily_hours": daily_hours,
            "days_per_week": days_per_week,
            "duration_months": duration_months,
            "focus_subject_ids": list(focus_set),
        },
        "baseline_comparison": {
            "baseline_exam_id": baseline_exam_id,
            "baseline_total_hours": baseline_available_hours,
            "scenario_total_hours": total_available_hours,
            "hours_delta": round(total_available_hours - baseline_available_hours, 1),
            "current_readiness_index": gap_data["readiness_index"],
            "projected_readiness_index": projected_readiness,
            "readiness_delta": round(projected_readiness - gap_data["readiness_index"], 1),
            "current_weighted_gap": gap_data["overall_weighted_gap"],
            "projected_weighted_gap": projected_gap,
            "gap_reduction": round(gap_data["overall_weighted_gap"] - projected_gap, 1),
        },
        "workload_assessment": {
            "estimated_required_hours": required_hours_est,
            "total_available_hours": total_available_hours,
            "effective_new_learning_hours": round(effective_gap_closing_hours, 1),
            "capacity_to_need_ratio": workload_ratio,
            "feasibility_status": feasibility_status,
            "transfer_index_from_source": transfer_data["effective_transfer_index"] if transfer_data else 100.0,
        },
        "projected_competencies": projected_competencies,
        "disclaimer": (
            "Scenario projections are transparent model approximations assuming consistent daily execution "
            "(75% gap closure, 25% revision/mock testing). They do not represent guaranteed exam outcomes or pass probabilities."
        ),
    }
