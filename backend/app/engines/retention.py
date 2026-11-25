"""
Retention Tracker Engine.
Tracks observed competency performance across dated assessments and builds revision queues.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy.orm import Session
from app.models import Competency, CompetencyEvidence, ExamCompetencyRequirement, Subject


def compute_retention_tracker(db: Session, user_id: int, exam_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    competencies = {c.id: c for c in db.query(Competency).all()}
    subjects = {s.id: s for s in db.query(Subject).all()}
    reqs = {
        r.competency_id: r
        for r in db.query(ExamCompetencyRequirement).filter(ExamCompetencyRequirement.exam_id == exam_id).all()
    }
    evidences = (
        db.query(CompetencyEvidence)
        .filter(CompetencyEvidence.user_id == user_id)
        .order_by(CompetencyEvidence.recorded_at.asc())
        .all()
    )

    by_comp: dict[str, list[CompetencyEvidence]] = defaultdict(list)
    for ev in evidences:
        by_comp[ev.competency_id].append(ev)

    items: list[dict[str, Any]] = []
    for cid, comp in competencies.items():
        if reqs and cid not in reqs:
            continue
        evs = by_comp.get(cid, [])
        req = reqs.get(cid)
        importance = req.weightage_percent if req else 5.0

        if not evs:
            items.append({
                "competency_id": cid,
                "competency_name": comp.name,
                "subject_name": subjects[comp.subject_id].name if comp.subject_id in subjects else comp.subject_id,
                "topic_name": comp.topic_name,
                "last_assessed_date": None,
                "days_since_assessed": None,
                "previous_performance": None,
                "current_estimate": 0.0,
                "retention_trend": "Needs Baseline",
                "revision_status": "Baseline Needed",
                "upcoming_revision_date": now.date().isoformat(),
                "urgency_score": round(60.0 + importance * 2.0, 1),
                "evidence_count": 0,
            })
            continue

        latest = evs[-1]
        prev = evs[-2] if len(evs) >= 2 else None
        latest_dt = latest.recorded_at if latest.recorded_at.tzinfo else latest.recorded_at.replace(tzinfo=timezone.utc)
        days_since = max(0, int((now - latest_dt).total_seconds() // 86400))

        curr_score = round(latest.observed_score, 1)
        prev_score = round(prev.observed_score, 1) if prev else None

        if prev is not None:
            delta = curr_score - prev_score
            if delta >= 5.0:
                trend = "Improving"
            elif delta <= -5.0:
                trend = "Declining"
            else:
                trend = "Stable"
        else:
            trend = "Single Observation"

        # Suggested review interval scales with current mastery & observation count
        interval_days = 4 if curr_score < 55 else (7 if curr_score < 75 else 12)
        if len(evs) >= 3 and trend in ("Improving", "Stable") and curr_score >= 75:
            interval_days += 4

        next_rev_dt = latest_dt + timedelta(days=interval_days)
        overdue_days = max(0, int((now - next_rev_dt).total_seconds() // 86400))

        if trend == "Declining" or overdue_days >= 3:
            status = "Revision Overdue"
        elif overdue_days >= 0 or days_since >= interval_days - 1:
            status = "Due Soon"
        else:
            status = "Retained"

        urgency = round(
            min(100.0, overdue_days * 7.0 + (100.0 - curr_score) * 0.45 + importance * 1.5),
            1,
        )

        items.append({
            "competency_id": cid,
            "competency_name": comp.name,
            "subject_name": subjects[comp.subject_id].name if comp.subject_id in subjects else comp.subject_id,
            "topic_name": comp.topic_name,
            "last_assessed_date": latest_dt.date().isoformat(),
            "days_since_assessed": days_since,
            "previous_performance": prev_score,
            "current_estimate": curr_score,
            "retention_trend": trend,
            "revision_status": status,
            "upcoming_revision_date": next_rev_dt.date().isoformat(),
            "urgency_score": urgency,
            "evidence_count": len(evs),
        })

    items.sort(key=lambda x: -x["urgency_score"])
    return {
        "exam_id": exam_id,
        "methodology_note": (
            "Retention status and revision intervals are derived from observed assessment performance "
            "trends and recency intervals — not biological memory-decay claims."
        ),
        "summary": {
            "overdue_count": sum(1 for i in items if i["revision_status"] == "Revision Overdue"),
            "due_soon_count": sum(1 for i in items if i["revision_status"] == "Due Soon"),
            "retained_count": sum(1 for i in items if i["revision_status"] == "Retained"),
            "baseline_needed_count": sum(1 for i in items if i["revision_status"] == "Baseline Needed"),
        },
        "items": items,
    }
