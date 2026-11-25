"""
Explainable Student Competency & Readiness Model.
Aggregates weighted assessment evidence with recency decay and confidence scaling.
"""

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session
from app.models import (
    AssessmentAttempt,
    Competency,
    CompetencyEvidence,
    Exam,
    ExamCompetencyRequirement,
    StudyTask,
    Subject,
)

SOURCE_WEIGHTS = {
    "mock_test": 1.35,
    "diagnostic": 1.15,
    "subject_test": 1.10,
    "topic_quiz": 1.00,
    "revision": 0.85,
    "study_task": 0.60,
}


def compute_readiness_profile(db: Session, user_id: int, exam_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    reqs = db.query(ExamCompetencyRequirement).filter(ExamCompetencyRequirement.exam_id == exam_id).all()
    competencies = {c.id: c for c in db.query(Competency).all()}
    subjects = {s.id: s for s in db.query(Subject).all()}

    evidences = (
        db.query(CompetencyEvidence)
        .filter(CompetencyEvidence.user_id == user_id)
        .order_by(CompetencyEvidence.recorded_at.asc())
        .all()
    )
    attempts = (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.user_id == user_id, AssessmentAttempt.status == "completed")
        .order_by(AssessmentAttempt.completed_at.asc())
        .all()
    )
    tasks = db.query(StudyTask).filter(StudyTask.user_id == user_id).all()

    by_comp: dict[str, list[CompetencyEvidence]] = defaultdict(list)
    for ev in evidences:
        by_comp[ev.competency_id].append(ev)

    competency_scores: dict[str, dict[str, Any]] = {}
    for comp_id, comp in competencies.items():
        comp_evs = by_comp.get(comp_id, [])
        if not comp_evs:
            competency_scores[comp_id] = {
                "competency_id": comp_id,
                "name": comp.name,
                "subject_id": comp.subject_id,
                "subject_name": subjects[comp.subject_id].name if comp.subject_id in subjects else comp.subject_id,
                "topic_name": comp.topic_name,
                "mastery_score": 0.0,
                "accuracy": 0.0,
                "speed_efficiency": 0.0,
                "confidence": 0.0,
                "evidence_count": 0,
                "last_assessed_at": None,
                "is_demo_only": False,
            }
            continue

        weighted_sum = 0.0
        weight_total = 0.0
        acc_sum = 0.0
        spd_sum = 0.0
        demo_only = all(ev.is_demo_seed for ev in comp_evs)

        for ev in comp_evs:
            rec_time = ev.recorded_at
            if rec_time.tzinfo is None:
                rec_time = rec_time.replace(tzinfo=timezone.utc)
            days_old = max(0.0, (now - rec_time).total_seconds() / 86400.0)
            recency_factor = math.exp(-days_old / 30.0)
            src_w = SOURCE_WEIGHTS.get(ev.source_type, 1.0) * (ev.weight or 1.0)
            eff_w = src_w * recency_factor

            weighted_sum += ev.observed_score * eff_w
            acc_sum += ev.accuracy * eff_w
            spd_sum += ev.speed_efficiency * eff_w
            weight_total += eff_w

        raw_mastery = weighted_sum / max(1e-6, weight_total)
        # Confidence increases with repeated distinct assessments
        confidence = round((1.0 - math.exp(-0.48 * len(comp_evs))) * 100.0, 1)
        last_dt = comp_evs[-1].recorded_at

        competency_scores[comp_id] = {
            "competency_id": comp_id,
            "name": comp.name,
            "subject_id": comp.subject_id,
            "subject_name": subjects[comp.subject_id].name if comp.subject_id in subjects else comp.subject_id,
            "topic_name": comp.topic_name,
            "mastery_score": round(min(100.0, max(0.0, raw_mastery)), 1),
            "accuracy": round(acc_sum / max(1e-6, weight_total), 1),
            "speed_efficiency": round(spd_sum / max(1e-6, weight_total), 1),
            "confidence": confidence,
            "evidence_count": len(comp_evs),
            "last_assessed_at": last_dt.isoformat() if last_dt else None,
            "is_demo_only": demo_only,
        }

    # Exam-aligned readiness rollup
    aligned_weighted = 0.0
    total_weightage = 0.0
    covered_count = 0
    subject_buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"score_sum": 0.0, "req_sum": 0.0, "weight_sum": 0.0, "count": 0}
    )

    for req in reqs:
        c_state = competency_scores.get(req.competency_id)
        if not c_state:
            continue
        # Ratio of student mastery to target depth, capped at 100
        alignment = min(100.0, (c_state["mastery_score"] / max(1.0, req.required_depth)) * 100.0)
        w = max(1.0, req.weightage_percent)
        aligned_weighted += alignment * w
        total_weightage += w
        if c_state["evidence_count"] > 0:
            covered_count += 1

        sid = c_state["subject_id"]
        subject_buckets[sid]["score_sum"] += c_state["mastery_score"] * w
        subject_buckets[sid]["req_sum"] += req.required_depth * w
        subject_buckets[sid]["weight_sum"] += w
        subject_buckets[sid]["count"] += 1

    readiness_index = round(aligned_weighted / max(1.0, total_weightage), 1)
    coverage_percent = round((covered_count / max(1, len(reqs))) * 100.0, 1)

    avg_accuracy = (
        round(sum(a.accuracy_percent for a in attempts) / len(attempts), 1)
        if attempts
        else 0.0
    )

    completed_tasks = sum(1 for t in tasks if t.status == "completed")
    total_tasks = len(tasks)
    consistency_score = (
        round(min(100.0, (completed_tasks / max(1, total_tasks)) * 70.0 + min(30.0, len(attempts) * 6.0)), 1)
        if (tasks or attempts)
        else 0.0
    )

    # Retention estimate based on recency of evidence across required competencies
    recent_7d = 0
    for req in reqs:
        c_state = competency_scores.get(req.competency_id)
        if c_state and c_state["last_assessed_at"]:
            dt = datetime.fromisoformat(c_state["last_assessed_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if (now - dt).total_seconds() <= 14 * 86400:
                recent_7d += 1
    retention_index = round((recent_7d / max(1, len(reqs))) * 100.0, 1) if evidences else 0.0

    subject_breakdown = []
    for sid, b in subject_buckets.items():
        wsum = max(1.0, b["weight_sum"])
        subject_breakdown.append({
            "subject_id": sid,
            "subject_name": subjects[sid].name if sid in subjects else sid,
            "demonstrated_score": round(b["score_sum"] / wsum, 1),
            "required_depth": round(b["req_sum"] / wsum, 1),
            "weightage_percent": round(b["weight_sum"], 1),
            "competency_count": b["count"],
        })
    subject_breakdown.sort(key=lambda x: x["weightage_percent"], reverse=True)

    has_only_demo_data = (len(attempts) > 0 and all(a.is_demo_seed for a in attempts)) or (
        len(evidences) > 0 and all(e.is_demo_seed for e in evidences)
    )

    return {
        "exam_id": exam_id,
        "exam_name": exam.name if exam else exam_id,
        "exam_short_name": exam.short_name if exam else exam_id,
        "readiness_index": readiness_index,
        "competency_coverage": coverage_percent,
        "retention_index": retention_index,
        "accuracy": avg_accuracy,
        "consistency": consistency_score,
        "assessments_completed": len(attempts),
        "evidence_points": len(evidences),
        "has_only_demo_data": has_only_demo_data,
        "subject_breakdown": subject_breakdown,
        "competencies": list(competency_scores.values()),
        "methodology": {
            "description": (
                "Readiness Index measures weighted competency alignment against the target examination's "
                "required depth profile. It is NOT a statistical probability of clearing the exam."
            ),
            "source_weights": SOURCE_WEIGHTS,
            "recency_half_life_days": 21,
            "confidence_formula": "1 - exp(-0.48 * evidence_count)",
        },
    }
