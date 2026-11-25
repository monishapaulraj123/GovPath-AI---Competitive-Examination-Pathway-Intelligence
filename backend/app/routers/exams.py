from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.engines.gap_analysis import compute_gap_analysis
from app.engines.knowledge_graph import CompetencyGraphEngine
from app.engines.readiness import compute_readiness_profile
from app.engines.transfer import analyze_knowledge_transfer
from app.models import Competency, Exam, ExamCompetencyRequirement, Subject, User
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["Exams & Knowledge Graph"])


@router.get("/exams")
def list_exams(
    search: Optional[str] = None,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exams = db.query(Exam).all()
    results = []
    for ex in exams:
        if category and category.lower() != "all" and ex.category.lower() != category.lower():
            continue
        if search:
            q = search.lower()
            if q not in ex.name.lower() and q not in ex.short_name.lower() and q not in ex.overview.lower():
                continue
        readiness = compute_readiness_profile(db, current_user.id, ex.id)
        results.append({
            "id": ex.id,
            "name": ex.name,
            "short_name": ex.short_name,
            "category": ex.category,
            "conducting_authority": ex.conducting_authority,
            "overview": ex.overview,
            "difficulty_index": ex.difficulty_index,
            "recommended_daily_hours": ex.recommended_daily_hours,
            "stages_count": len(ex.stages or []),
            "student_readiness_index": readiness["readiness_index"],
            "competency_coverage": readiness["competency_coverage"],
        })
    return {"exams": results}


@router.get("/exams/compare")
def compare_exams(
    exam_ids: str = Query(..., description="Comma-separated exam IDs"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ids = [i.strip() for i in exam_ids.split(",") if i.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Select at least 2 examinations to compare")

    exams = {e.id: e for e in db.query(Exam).filter(Exam.id.in_(ids)).all()}
    if len(exams) < 2:
        raise HTTPException(status_code=404, detail="One or more examinations not found")

    subjects = {s.id: s.name for s in db.query(Subject).all()}
    competencies = {c.id: c for c in db.query(Competency).all()}
    reqs = db.query(ExamCompetencyRequirement).filter(ExamCompetencyRequirement.exam_id.in_(ids)).all()

    matrix: dict[str, dict] = {}
    for req in reqs:
        comp = competencies.get(req.competency_id)
        if not comp:
            continue
        row = matrix.setdefault(
            req.competency_id,
            {
                "competency_id": comp.id,
                "competency_name": comp.name,
                "subject_id": comp.subject_id,
                "subject_name": subjects.get(comp.subject_id, comp.subject_id),
                "topic_name": comp.topic_name,
                "requirements": {},
            },
        )
        row["requirements"][req.exam_id] = {
            "required_depth": req.required_depth,
            "weightage_percent": req.weightage_percent,
            "subject_label": req.exam_subject_label,
        }

    exam_summaries = []
    for eid in ids:
        ex = exams.get(eid)
        if not ex:
            continue
        readiness = compute_readiness_profile(db, current_user.id, eid)
        gaps = compute_gap_analysis(db, current_user.id, eid)
        exam_summaries.append({
            "id": ex.id,
            "name": ex.name,
            "short_name": ex.short_name,
            "category": ex.category,
            "conducting_authority": ex.conducting_authority,
            "stages": ex.stages,
            "eligibility_summary": ex.eligibility_summary,
            "recommended_daily_hours": ex.recommended_daily_hours,
            "difficulty_index": ex.difficulty_index,
            "readiness_index": readiness["readiness_index"],
            "overall_gap": gaps["overall_weighted_gap"],
        })

    # Pairwise transfer summary from first selected exam to others
    pairwise_transfer = [
        analyze_knowledge_transfer(db, current_user.id, ids[0], other_id)
        for other_id in ids[1:]
        if other_id in exams
    ]

    return {
        "exams": exam_summaries,
        "competency_matrix": list(matrix.values()),
        "pairwise_transfer": pairwise_transfer,
    }


@router.get("/exams/{exam_id}")
def get_exam_detail(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ex = db.query(Exam).filter(Exam.id == exam_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Examination not found")

    reqs = db.query(ExamCompetencyRequirement).filter(ExamCompetencyRequirement.exam_id == exam_id).all()
    competencies = {c.id: c for c in db.query(Competency).all()}
    subjects = {s.id: s for s in db.query(Subject).all()}
    readiness = compute_readiness_profile(db, current_user.id, exam_id)
    student_comp = {c["competency_id"]: c for c in readiness["competencies"]}

    syllabus_items = []
    for r in reqs:
        comp = competencies.get(r.competency_id)
        if not comp:
            continue
        st = student_comp.get(r.competency_id, {})
        syllabus_items.append({
            "competency_id": comp.id,
            "competency_name": comp.name,
            "subject_id": comp.subject_id,
            "subject_name": subjects[comp.subject_id].name if comp.subject_id in subjects else comp.subject_id,
            "topic_name": comp.topic_name,
            "subtopics": comp.subtopics,
            "exam_subject_label": r.exam_subject_label,
            "required_depth": r.required_depth,
            "weightage_percent": r.weightage_percent,
            "stage_relevance": r.stage_relevance,
            "student_mastery": st.get("mastery_score", 0.0),
        })

    return {
        "id": ex.id,
        "name": ex.name,
        "short_name": ex.short_name,
        "category": ex.category,
        "conducting_authority": ex.conducting_authority,
        "overview": ex.overview,
        "eligibility_summary": ex.eligibility_summary,
        "verification_note": ex.verification_note,
        "official_sources": ex.official_sources,
        "stages": ex.stages,
        "exam_pattern": ex.exam_pattern,
        "preparation_resources": ex.preparation_resources,
        "difficulty_index": ex.difficulty_index,
        "recommended_daily_hours": ex.recommended_daily_hours,
        "readiness_alignment": {
            "readiness_index": readiness["readiness_index"],
            "competency_coverage": readiness["competency_coverage"],
            "subject_breakdown": readiness["subject_breakdown"],
        },
        "syllabus_competencies": syllabus_items,
    }


@router.get("/knowledge-graph")
def get_knowledge_graph(
    exam_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    readiness = compute_readiness_profile(db, current_user.id, exam_id or "UPSC_CSE")
    student_scores = {c["competency_id"]: c["mastery_score"] for c in readiness["competencies"]}
    graph = CompetencyGraphEngine(db)
    return graph.get_full_graph(exam_id=exam_id, subject_id=subject_id, student_scores=student_scores)


@router.get("/knowledge-graph/competency/{competency_id}")
def get_competency_node(
    competency_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    graph = CompetencyGraphEngine(db)
    return graph.get_competency_neighbors(competency_id)
