"""
Exam-to-Exam Knowledge Transfer Analysis Engine.
Uses Competency Graph structural mappings, required depth deltas, and student evidence.
"""

from typing import Any
from sqlalchemy.orm import Session
from app.engines.knowledge_graph import CompetencyGraphEngine
from app.engines.readiness import compute_readiness_profile
from app.models import Competency, Exam

HOURS_PER_GAP_POINT_FACTOR = 0.32  # Model assumption: ~0.32 hrs per depth-gap point scaled by base hours


def analyze_knowledge_transfer(
    db: Session,
    user_id: int,
    source_exam_id: str,
    target_exam_id: str,
) -> dict[str, Any]:
    graph = CompetencyGraphEngine(db)
    overlap = graph.query_shared_competencies(source_exam_id, target_exam_id)
    readiness = compute_readiness_profile(db, user_id, target_exam_id)
    student_comp = {c["competency_id"]: c for c in readiness["competencies"]}
    competencies = {c.id: c for c in db.query(Competency).all()}

    source_exam = db.query(Exam).filter(Exam.id == source_exam_id).first()
    target_exam = db.query(Exam).filter(Exam.id == target_exam_id).first()

    items: list[dict[str, Any]] = []
    counts = {
        "Fully Transferable": 0,
        "Partially Transferable": 0,
        "Requires Reinforcement": 0,
        "Not Covered": 0,
    }
    total_estimated_hours = 0.0
    transferable_weight = 0.0
    total_target_weight = 0.0
    evidence_backed_shared_count = 0
    unassessed_shared_count = 0
    verified_mastery_weight = 0.0

    # Shared competencies between source and target
    for sh in overlap["shared"]:
        cid = sh["competency_id"]
        comp = competencies.get(cid)
        comp_state = student_comp.get(cid, {})
        student_score = float(comp_state.get("mastery_score", 0.0))
        evidence_count = int(comp_state.get("evidence_count", 0))
        target_depth = float(sh["target_depth"])
        source_depth = float(sh["source_depth"])
        weight = float(sh["target_weightage"])
        total_target_weight += weight

        if evidence_count > 0:
            evidence_backed_shared_count += 1
        else:
            unassessed_shared_count += 1

        gap_to_target = max(0.0, target_depth - student_score)
        depth_mismatch = round(target_depth - source_depth, 1)

        if source_depth >= target_depth - 5 and student_score >= target_depth * 0.75:
            classification = "Fully Transferable"
            transfer_credit = 1.0
        elif student_score >= target_depth * 0.45 and depth_mismatch <= 15:
            classification = "Partially Transferable"
            transfer_credit = 0.6
        else:
            classification = "Requires Reinforcement"
            transfer_credit = 0.35

        counts[classification] += 1
        transferable_weight += weight * transfer_credit
        if evidence_count > 0:
            verified_mastery_weight += weight * min(1.0, student_score / max(1.0, target_depth))

        base_hrs = comp.base_learning_hours if comp else 15.0
        est_hours = round(gap_to_target * HOURS_PER_GAP_POINT_FACTOR * (base_hrs / 16.0), 1)
        total_estimated_hours += est_hours

        items.append({
            "competency_id": cid,
            "competency_name": sh["competency_name"],
            "subject_id": sh["subject_id"],
            "topic_name": sh["topic_name"],
            "classification": classification,
            "source_required_depth": source_depth,
            "target_required_depth": target_depth,
            "depth_mismatch": depth_mismatch,
            "student_mastery": round(student_score, 1),
            "evidence_count": evidence_count,
            "remaining_gap": round(gap_to_target, 1),
            "weightage_percent": weight,
            "estimated_additional_hours": est_hours,
        })

    # Competencies in target exam NOT covered in source exam
    for miss in overlap["target_only"]:
        cid = miss["competency_id"]
        comp = competencies.get(cid)
        comp_state = student_comp.get(cid, {})
        student_score = float(comp_state.get("mastery_score", 0.0))
        evidence_count = int(comp_state.get("evidence_count", 0))
        target_depth = float(miss["target_depth"])
        weight = float(miss["target_weightage"])
        total_target_weight += weight
        gap_to_target = max(0.0, target_depth - student_score)

        classification = "Not Covered"
        counts[classification] += 1
        if evidence_count > 0:
            verified_mastery_weight += weight * min(1.0, student_score / max(1.0, target_depth))

        base_hrs = comp.base_learning_hours if comp else 16.0
        est_hours = round(gap_to_target * HOURS_PER_GAP_POINT_FACTOR * (base_hrs / 15.0), 1)
        total_estimated_hours += est_hours

        items.append({
            "competency_id": cid,
            "competency_name": miss["competency_name"],
            "subject_id": miss["subject_id"],
            "topic_name": miss["topic_name"],
            "classification": classification,
            "source_required_depth": 0.0,
            "target_required_depth": target_depth,
            "depth_mismatch": target_depth,
            "student_mastery": round(student_score, 1),
            "evidence_count": evidence_count,
            "remaining_gap": round(gap_to_target, 1),
            "weightage_percent": weight,
            "estimated_additional_hours": est_hours,
        })

    effective_transfer_index = round((transferable_weight / max(1.0, total_target_weight)) * 100.0, 1)
    verified_mastery_transfer_percent = round(
        (verified_mastery_weight / max(1.0, total_target_weight)) * 100.0, 1
    )
    assessments_completed = int(readiness.get("assessments_completed", 0))
    if assessments_completed == 0 and evidence_backed_shared_count == 0:
        evidence_basis = "structural_baseline_only"
        transfer_index_label = "Model-Estimated Potential Transfer Index (Structural Baseline Only)"
        transfer_index_disclosure = (
            f"No completed assessment evidence is recorded. The {effective_transfer_index}% index reflects "
            f"a theoretical 0.35 baseline structural credit assigned to shared competencies between "
            f"{source_exam_id} and {target_exam_id}, NOT measured individual proficiency "
            f"(verified individual transfer evidence: {verified_mastery_transfer_percent}%)."
        )
    elif unassessed_shared_count > 0 or len(overlap["target_only"]) > 0:
        evidence_basis = "partial_assessment_evidence"
        transfer_index_label = "Partially Evidence-Weighted Potential Transfer Index"
        transfer_index_disclosure = (
            f"Combines verified assessment evidence on {evidence_backed_shared_count} shared competenc(ies) "
            f"with a 0.35 structural baseline credit on {unassessed_shared_count} unassessed shared competenc(ies). "
            f"Verified assessment-only alignment across target weightage is {verified_mastery_transfer_percent}%."
        )
    else:
        evidence_basis = "evidence_backed"
        transfer_index_label = "Evidence-Weighted Transfer Index"
        transfer_index_disclosure = (
            f"All shared competencies have recorded assessment evidence "
            f"({evidence_backed_shared_count} shared competencies assessed)."
        )

    class_order = {
        "Fully Transferable": 0,
        "Partially Transferable": 1,
        "Requires Reinforcement": 2,
        "Not Covered": 3,
    }
    items.sort(key=lambda x: (class_order.get(x["classification"], 4), -x["weightage_percent"]))

    return {
        "source_exam_id": source_exam_id,
        "source_exam_name": source_exam.short_name if source_exam else source_exam_id,
        "target_exam_id": target_exam_id,
        "target_exam_name": target_exam.short_name if target_exam else target_exam_id,
        "structural_overlap_percent": overlap["structural_overlap_percent"],
        "effective_transfer_index": effective_transfer_index,
        "verified_mastery_transfer_percent": verified_mastery_transfer_percent,
        "assessments_completed": assessments_completed,
        "evidence_backed_shared_count": evidence_backed_shared_count,
        "unassessed_shared_count": unassessed_shared_count,
        "evidence_basis": evidence_basis,
        "transfer_index_label": transfer_index_label,
        "transfer_index_disclosure": transfer_index_disclosure,
        "classification_counts": counts,
        "estimated_additional_hours": round(total_estimated_hours, 1),
        "effort_model_note": (
            "Estimated additional hours are model-generated approximations calculated from remaining "
            "competency depth gaps and baseline topic learning hours (0.32 hrs per gap point baseline). "
            "Actual time varies by individual pace and revision frequency."
        ),
        "competencies": items,
        "source_only_competencies": overlap["source_only"],
    }
