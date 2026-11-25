from collections import defaultdict
from datetime import datetime, timezone
import random
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.engines.diagnosis import classify_answer_error
from app.models import (
    AssessmentAttempt,
    AttemptAnswer,
    Competency,
    CompetencyEvidence,
    Exam,
    Question,
    SavedQuestion,
    StudentProfile,
    Subject,
    User,
)
from app.schemas import SaveQuestionRequest, StartAssessmentRequest, SubmitAssessmentRequest
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["Assessments & Practice"])


@router.get("/assessments")
def list_assessments(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    attempts = (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.user_id == current_user.id)
        .order_by(AssessmentAttempt.started_at.desc())
        .all()
    )
    exams = {e.id: e.short_name for e in db.query(Exam).all()}
    subjects = [{"id": s.id, "name": s.name} for s in db.query(Subject).all()]
    competencies = [{"id": c.id, "name": c.name, "subject_id": c.subject_id, "topic_name": c.topic_name} for c in db.query(Competency).all()]

    return {
        "attempts": [
            {
                "id": a.id,
                "exam_id": a.exam_id,
                "exam_short_name": exams.get(a.exam_id, a.exam_id),
                "assessment_type": a.assessment_type,
                "title": a.title,
                "status": a.status,
                "score_percent": a.score_percent,
                "accuracy_percent": a.accuracy_percent,
                "total_questions": a.total_questions,
                "correct_count": a.correct_count,
                "incorrect_count": a.incorrect_count,
                "unanswered_count": a.unanswered_count,
                "time_limit_sec": a.time_limit_sec,
                "time_taken_sec": a.time_taken_sec,
                "is_demo_seed": a.is_demo_seed,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in attempts
        ],
        "subjects": subjects,
        "competencies": competencies,
    }


@router.post("/assessments/start")
def start_assessment(
    payload: StartAssessmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == payload.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Examination not found")

    all_qs = db.query(Question).all()
    # Filter by competency / subject / exam mapping with sensible fallbacks
    pool = [q for q in all_qs if payload.exam_id in (q.exam_mappings or [])]
    if not pool:
        pool = all_qs

    if payload.competency_id:
        comp_pool = [q for q in all_qs if q.competency_id == payload.competency_id]
        if comp_pool:
            pool = comp_pool
    elif payload.subject_id:
        subj_pool = [q for q in pool if q.subject_id == payload.subject_id] or [
            q for q in all_qs if q.subject_id == payload.subject_id
        ]
        if subj_pool:
            pool = subj_pool

    # For weak/revision mode, prioritize previously missed competencies
    if payload.assessment_type == "revision":
        missed_ids = {
            a.competency_id
            for a in db.query(AttemptAnswer)
            .join(AssessmentAttempt, AttemptAnswer.attempt_id == AssessmentAttempt.id)
            .filter(AssessmentAttempt.user_id == current_user.id, AttemptAnswer.is_correct == False)
            .all()
        }
        weak_pool = [q for q in pool if q.competency_id in missed_ids]
        if weak_pool:
            pool = weak_pool + [q for q in pool if q not in weak_pool]

    selected = pool[: payload.question_count]
    if len(selected) < min(payload.question_count, len(all_qs)):
        extras = [q for q in all_qs if q not in selected]
        random.shuffle(extras)
        selected.extend(extras[: payload.question_count - len(selected)])

    type_titles = {
        "diagnostic": f"{exam.short_name} Diagnostic Assessment",
        "mock_test": f"{exam.short_name} Simulated Mock Test",
        "subject_test": f"{exam.short_name} Subject Assessment",
        "topic_quiz": f"{exam.short_name} Topic Quiz",
        "revision": f"{exam.short_name} Spaced Revision Check",
    }
    title = type_titles.get(payload.assessment_type, f"{exam.short_name} Assessment")
    time_limit = payload.time_limit_sec or (len(selected) * 75)

    attempt = AssessmentAttempt(
        user_id=current_user.id,
        exam_id=payload.exam_id,
        assessment_type=payload.assessment_type,
        title=title,
        question_ids=[q.id for q in selected],
        status="in_progress",
        total_questions=len(selected),
        time_limit_sec=time_limit,
        is_demo_seed=False,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    subjects = {s.id: s.name for s in db.query(Subject).all()}
    competencies = {c.id: c.name for c in db.query(Competency).all()}

    return {
        "attempt_id": attempt.id,
        "exam_id": attempt.exam_id,
        "exam_short_name": exam.short_name,
        "assessment_type": attempt.assessment_type,
        "title": attempt.title,
        "time_limit_sec": attempt.time_limit_sec,
        "questions": [
            {
                "id": q.id,
                "prompt": q.prompt,
                "options": q.options,
                "subject_id": q.subject_id,
                "subject_name": subjects.get(q.subject_id, q.subject_id),
                "topic_name": q.topic_name,
                "competency_id": q.competency_id,
                "competency_name": competencies.get(q.competency_id, q.competency_id),
                "difficulty": q.difficulty,
                "expected_time_sec": q.expected_time_sec,
                "source_type": q.source_type,
                "source_label": q.source_label,
            }
            for q in selected
        ],
    }


@router.post("/assessments/{attempt_id}/submit")
def submit_assessment(
    attempt_id: int,
    payload: SubmitAssessmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempt = (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.id == attempt_id, AssessmentAttempt.user_id == current_user.id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Assessment attempt not found")
    if attempt.status == "completed":
        return get_assessment_detail(attempt_id, current_user, db)

    q_map = {q.id: q for q in db.query(Question).filter(Question.id.in_(attempt.question_ids)).all()}
    ans_by_qid = {a.question_id: a for a in payload.answers}

    # Historical competency errors for pattern detection
    prior_answers = (
        db.query(AttemptAnswer)
        .join(AssessmentAttempt, AttemptAnswer.attempt_id == AssessmentAttempt.id)
        .filter(AssessmentAttempt.user_id == current_user.id, AssessmentAttempt.status == "completed")
        .all()
    )
    comp_error_counts: dict[str, int] = defaultdict(int)
    prior_correct_comp: set[str] = set()
    for pa in prior_answers:
        if pa.is_correct:
            prior_correct_comp.add(pa.competency_id)
        else:
            comp_error_counts[pa.competency_id] += 1

    correct_count = 0
    incorrect_count = 0
    unanswered_count = 0
    comp_perf: dict[str, list[tuple[bool, int, int]]] = defaultdict(list)

    for qid in attempt.question_ids:
        q = q_map.get(qid)
        if not q:
            continue
        item = ans_by_qid.get(qid)
        sel = item.selected_index if item else None
        time_sec = item.time_spent_sec if item else 45
        marked = item.marked_for_review if item else False
        conf = item.confidence_level if item else "medium"

        is_correct = sel is not None and sel == q.correct_index
        if sel is None:
            unanswered_count += 1
        elif is_correct:
            correct_count += 1
        else:
            incorrect_count += 1
            comp_error_counts[q.competency_id] += 1

        ans_row = AttemptAnswer(
            attempt_id=attempt.id,
            question_id=q.id,
            competency_id=q.competency_id,
            selected_index=sel,
            is_correct=is_correct,
            marked_for_review=marked,
            time_spent_sec=time_sec,
            confidence_level=conf,
        )
        if not is_correct:
            ans_row.error_category = classify_answer_error(
                ans_row, q, comp_error_counts, q.competency_id in prior_correct_comp
            )
        db.add(ans_row)
        comp_perf[q.competency_id].append((is_correct, time_sec, q.expected_time_sec))

    total_q = max(1, len(attempt.question_ids))
    answered = correct_count + incorrect_count
    attempt.correct_count = correct_count
    attempt.incorrect_count = incorrect_count
    attempt.unanswered_count = unanswered_count
    attempt.score_percent = round((correct_count / total_q) * 100.0, 1)
    attempt.accuracy_percent = round((correct_count / max(1, answered)) * 100.0, 1) if answered else 0.0
    attempt.time_taken_sec = payload.total_time_sec
    attempt.status = "completed"
    attempt.completed_at = datetime.now(timezone.utc)

    # Record Competency Evidence for Readiness & Retention engines
    now = datetime.now(timezone.utc)
    for cid, rows in comp_perf.items():
        acc = (sum(1 for r in rows if r[0]) / len(rows)) * 100.0
        avg_spd = sum(min(1.25, r[2] / max(1, r[1])) for r in rows) / len(rows)
        spd_eff = round(min(100.0, avg_spd * 82.0), 1)
        # Observed score blends accuracy and speed efficiency
        obs_score = round(min(98.0, max(18.0, acc * 0.85 + spd_eff * 0.15)), 1)
        db.add(
            CompetencyEvidence(
                user_id=current_user.id,
                competency_id=cid,
                source_type=attempt.assessment_type,
                attempt_id=attempt.id,
                observed_score=obs_score,
                accuracy=round(acc, 1),
                speed_efficiency=spd_eff,
                weight=1.0,
                is_demo_seed=False,
                recorded_at=now,
            )
        )

    db.commit()
    return get_assessment_detail(attempt_id, current_user, db)


@router.get("/assessments/{attempt_id}")
def get_assessment_detail(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempt = (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.id == attempt_id, AssessmentAttempt.user_id == current_user.id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Assessment attempt not found")

    q_map = {q.id: q for q in db.query(Question).filter(Question.id.in_(attempt.question_ids)).all()}
    answers = db.query(AttemptAnswer).filter(AttemptAnswer.attempt_id == attempt.id).all()
    ans_map = {a.question_id: a for a in answers}
    subjects = {s.id: s.name for s in db.query(Subject).all()}
    competencies = {c.id: c.name for c in db.query(Competency).all()}

    topic_breakdown: dict[str, dict] = defaultdict(lambda: {"total": 0, "correct": 0})
    comp_breakdown: dict[str, dict] = defaultdict(lambda: {"name": "", "total": 0, "correct": 0})
    question_review = []

    for qid in attempt.question_ids:
        q = q_map.get(qid)
        if not q:
            continue
        ans = ans_map.get(qid)
        is_ok = ans.is_correct if ans else False

        topic_breakdown[q.topic_name]["total"] += 1
        topic_breakdown[q.topic_name]["correct"] += 1 if is_ok else 0

        comp_breakdown[q.competency_id]["name"] = competencies.get(q.competency_id, q.competency_id)
        comp_breakdown[q.competency_id]["total"] += 1
        comp_breakdown[q.competency_id]["correct"] += 1 if is_ok else 0

        question_review.append({
            "question_id": q.id,
            "prompt": q.prompt,
            "options": q.options,
            "correct_index": q.correct_index,
            "selected_index": ans.selected_index if ans else None,
            "is_correct": is_ok,
            "marked_for_review": ans.marked_for_review if ans else False,
            "time_spent_sec": ans.time_spent_sec if ans else 0,
            "expected_time_sec": q.expected_time_sec,
            "error_category": ans.error_category if ans else None,
            "explanation": q.explanation,
            "subject_name": subjects.get(q.subject_id, q.subject_id),
            "topic_name": q.topic_name,
            "competency_id": q.competency_id,
            "competency_name": competencies.get(q.competency_id, q.competency_id),
            "difficulty": q.difficulty,
            "source_type": q.source_type,
        })

    return {
        "attempt": {
            "id": attempt.id,
            "exam_id": attempt.exam_id,
            "assessment_type": attempt.assessment_type,
            "title": attempt.title,
            "status": attempt.status,
            "score_percent": attempt.score_percent,
            "accuracy_percent": attempt.accuracy_percent,
            "total_questions": attempt.total_questions,
            "correct_count": attempt.correct_count,
            "incorrect_count": attempt.incorrect_count,
            "unanswered_count": attempt.unanswered_count,
            "time_taken_sec": attempt.time_taken_sec,
            "time_limit_sec": attempt.time_limit_sec,
            "is_demo_seed": attempt.is_demo_seed,
            "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
        },
        "topic_performance": [
            {
                "topic": t,
                "total": v["total"],
                "correct": v["correct"],
                "accuracy_percent": round((v["correct"] / max(1, v["total"])) * 100.0, 1),
            }
            for t, v in topic_breakdown.items()
        ],
        "competency_performance": [
            {
                "competency_id": cid,
                "competency_name": v["name"],
                "total": v["total"],
                "correct": v["correct"],
                "accuracy_percent": round((v["correct"] / max(1, v["total"])) * 100.0, 1),
            }
            for cid, v in comp_breakdown.items()
        ],
        "questions": question_review,
    }


@router.get("/practice/questions")
def list_practice_questions(
    mode: str = "all",  # all, weak, incorrect, saved
    subject_id: Optional[str] = None,
    competency_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    questions = db.query(Question).all()
    subjects = {s.id: s.name for s in db.query(Subject).all()}
    competencies = {c.id: c.name for c in db.query(Competency).all()}
    saved_map = {
        sq.question_id: sq.note
        for sq in db.query(SavedQuestion).filter(SavedQuestion.user_id == current_user.id).all()
    }
    incorrect_qids = {
        a.question_id
        for a in db.query(AttemptAnswer)
        .join(AssessmentAttempt, AttemptAnswer.attempt_id == AssessmentAttempt.id)
        .filter(AssessmentAttempt.user_id == current_user.id, AttemptAnswer.is_correct == False)
        .all()
    }

    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    primary_exam = profile.primary_target_exam if profile else "UPSC_CSE"

    if mode == "saved":
        questions = [q for q in questions if q.id in saved_map]
    elif mode == "incorrect":
        questions = [q for q in questions if q.id in incorrect_qids]
    elif mode == "weak":
        weak_cids = {
            a.competency_id
            for a in db.query(AttemptAnswer)
            .join(AssessmentAttempt, AttemptAnswer.attempt_id == AssessmentAttempt.id)
            .filter(AssessmentAttempt.user_id == current_user.id, AttemptAnswer.is_correct == False)
            .all()
        }
        if weak_cids:
            questions = [q for q in questions if q.competency_id in weak_cids]

    if subject_id and subject_id != "ALL":
        questions = [q for q in questions if q.subject_id == subject_id]
    if competency_id:
        questions = [q for q in questions if q.competency_id == competency_id]

    return {
        "primary_exam": primary_exam,
        "questions": [
            {
                "id": q.id,
                "prompt": q.prompt,
                "options": q.options,
                "correct_index": q.correct_index,
                "explanation": q.explanation,
                "subject_id": q.subject_id,
                "subject_name": subjects.get(q.subject_id, q.subject_id),
                "topic_name": q.topic_name,
                "competency_id": q.competency_id,
                "competency_name": competencies.get(q.competency_id, q.competency_id),
                "difficulty": q.difficulty,
                "exam_mappings": q.exam_mappings,
                "source_type": q.source_type,
                "is_saved": q.id in saved_map,
                "saved_note": saved_map.get(q.id, ""),
                "previously_missed": q.id in incorrect_qids,
            }
            for q in questions
        ],
    }


@router.post("/practice/save")
def toggle_save_question(
    payload: SaveQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(SavedQuestion)
        .filter(SavedQuestion.user_id == current_user.id, SavedQuestion.question_id == payload.question_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        return {"saved": False}

    db.add(SavedQuestion(user_id=current_user.id, question_id=payload.question_id, note=payload.note))
    db.commit()
    return {"saved": True}
