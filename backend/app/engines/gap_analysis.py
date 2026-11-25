"""
Deterministic Gap Analysis Engine.
Compares Target Exam Competency Requirements against Student Demonstrated Competency Evidence.
"""

from collections import defaultdict
from typing import Any
from sqlalchemy.orm import Session
from app.engines.readiness import compute_readiness_profile
from app.models import Competency, Exam, ExamCompetencyRequirement, Subject


def classify_gap_priority(gap: float, weightage: float, evidence_count: int) -> str:
    weighted_impact = gap * (1.0 + weightage / 20.0)
    if evidence_count == 0 and gap >= 50:
        return "Critical"
    if gap >= 30 or weighted_impact >= 40:
        return "High"
    if gap >= 15:
        return "Moderate"
    if gap > 0:
        return "Low"
    return "On Track"


def compute_gap_analysis(db: Session, user_id: int, exam_id: str) -> dict[str, Any]:
    readiness = compute_readiness_profile(db, user_id, exam_id)
    comp_map = {c["competency_id"]: c for c in readiness["competencies"]}

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    reqs = db.query(ExamCompetencyRequirement).filter(ExamCompetencyRequirement.exam_id == exam_id).all()
    competencies = {c.id: c for c in db.query(Competency).all()}
    subjects = {s.id: s for s in db.query(Subject).all()}

    competency_gaps: list[dict[str, Any]] = []
    subject_rollup: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"req_total": 0.0, "curr_total": 0.0, "gap_total": 0.0, "count": 0, "weight": 0.0}
    )

    for req in reqs:
        comp = competencies.get(req.competency_id)
        if not comp:
            continue
        state = comp_map.get(req.competency_id, {})
        current_level = float(state.get("mastery_score", 0.0))
        evidence_count = int(state.get("evidence_count", 0))
        confidence = float(state.get("confidence", 0.0))
        gap = round(max(0.0, req.required_depth - current_level), 1)
        priority = classify_gap_priority(gap, req.weightage_percent, evidence_count)

        if evidence_count == 0:
            intervention = f"Take a baseline diagnostic or topic quiz on {comp.topic_name} to establish verified competency evidence."
        elif gap >= 30:
            intervention = f"Structured deep study on {', '.join(comp.subtopics[:2])} followed by timed MCQ drills."
        elif gap >= 15:
            intervention = f"Targeted reinforcement and mixed-difficulty practice on {comp.topic_name}."
        elif gap > 0:
            intervention = f"Periodic retrieval practice to close the final {gap}-point depth margin."
        else:
            intervention = "Target depth achieved; schedule periodic retention checks."

        competency_gaps.append({
            "competency_id": comp.id,
            "competency_name": comp.name,
            "subject_id": comp.subject_id,
            "subject_name": subjects[comp.subject_id].name if comp.subject_id in subjects else comp.subject_id,
            "topic_name": comp.topic_name,
            "exam_subject_label": req.exam_subject_label,
            "stage_relevance": req.stage_relevance,
            "required_level": req.required_depth,
            "current_evidence": current_level,
            "gap": gap,
            "depth_mismatch": round(req.required_depth - current_level, 1),
            "weightage_percent": req.weightage_percent,
            "confidence": confidence,
            "evidence_count": evidence_count,
            "priority": priority,
            "recommended_intervention": intervention,
        })

        sb = subject_rollup[comp.subject_id]
        sb["req_total"] += req.required_depth
        sb["curr_total"] += current_level
        sb["gap_total"] += gap
        sb["count"] += 1
        sb["weight"] += req.weightage_percent

    priority_order = {"Critical": 0, "High": 1, "Moderate": 2, "Low": 3, "On Track": 4}
    competency_gaps.sort(key=lambda x: (priority_order.get(x["priority"], 5), -x["gap"], -x["weightage_percent"]))

    subject_gaps = []
    for sid, sb in subject_rollup.items():
        cnt = max(1, sb["count"])
        avg_gap = round(sb["gap_total"] / cnt, 1)
        subject_gaps.append({
            "subject_id": sid,
            "subject_name": subjects[sid].name if sid in subjects else sid,
            "avg_required": round(sb["req_total"] / cnt, 1),
            "avg_current": round(sb["curr_total"] / cnt, 1),
            "avg_gap": avg_gap,
            "weightage_percent": round(sb["weight"], 1),
            "priority": classify_gap_priority(avg_gap, sb["weight"], 1),
        })
    subject_gaps.sort(key=lambda x: -x["avg_gap"])

    missing_competencies = [g for g in competency_gaps if g["evidence_count"] == 0]
    overall_gap = round(
        sum(g["gap"] * g["weightage_percent"] for g in competency_gaps)
        / max(1.0, sum(g["weightage_percent"] for g in competency_gaps)),
        1,
    )

    return {
        "exam_id": exam_id,
        "exam_name": exam.name if exam else exam_id,
        "exam_short_name": exam.short_name if exam else exam_id,
        "overall_weighted_gap": overall_gap,
        "readiness_index": readiness["readiness_index"],
        "has_only_demo_data": readiness["has_only_demo_data"],
        "priority_counts": {
            p: sum(1 for g in competency_gaps if g["priority"] == p)
            for p in ["Critical", "High", "Moderate", "Low", "On Track"]
        },
        "subject_gaps": subject_gaps,
        "competency_gaps": competency_gaps,
        "missing_competencies": missing_competencies,
        "top_priorities": competency_gaps[:5],
    }
