"""
Rule-Based Performance Diagnosis Engine.
Analyzes actual attempt answers, timing, unanswered rates, difficulty splits, and repeated competency errors.
"""

from collections import defaultdict
from typing import Any
from sqlalchemy.orm import Session
from app.models import AssessmentAttempt, AttemptAnswer, Competency, Question, Subject


def classify_answer_error(
    answer: AttemptAnswer,
    question: Question,
    comp_error_counts: dict[str, int],
    prior_correct_in_comp: bool,
) -> str:
    if answer.selected_index is None:
        return "Time-Management Difficulty"
    if comp_error_counts.get(question.competency_id, 0) >= 2:
        return "Repeated Error Pattern"
    if prior_correct_in_comp:
        return "Retention Deficiency"
    if answer.time_spent_sec > max(75, int(question.expected_time_sec * 1.35)):
        return "Time-Management Difficulty"
    if question.difficulty == "easy":
        return "Question Interpretation Difficulty"
    if question.difficulty == "hard":
        return "Application Difficulty"
    return "Knowledge Deficiency"


def compute_performance_diagnosis(db: Session, user_id: int) -> dict[str, Any]:
    attempts = (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.user_id == user_id, AssessmentAttempt.status == "completed")
        .order_by(AssessmentAttempt.completed_at.desc())
        .all()
    )
    competencies = {c.id: c for c in db.query(Competency).all()}
    subjects = {s.id: s for s in db.query(Subject).all()}
    questions = {q.id: q for q in db.query(Question).all()}

    if not attempts:
        return {
            "has_data": False,
            "total_attempts": 0,
            "error_category_breakdown": {},
            "difficulty_performance": {},
            "repeated_weak_competencies": [],
            "detailed_mistakes": [],
            "recommendations": [
                "Complete at least one diagnostic assessment or topic quiz to generate evidence-backed error diagnostics."
            ],
        }

    attempt_ids = [a.id for a in attempts]
    answers = (
        db.query(AttemptAnswer)
        .filter(AttemptAnswer.attempt_id.in_(attempt_ids))
        .all()
    )
    attempt_map = {a.id: a for a in attempts}

    comp_error_counts: dict[str, int] = defaultdict(int)
    comp_ever_correct: set[str] = set()
    for ans in answers:
        if ans.is_correct:
            comp_ever_correct.add(ans.competency_id)
        else:
            comp_error_counts[ans.competency_id] += 1

    category_counts: dict[str, int] = defaultdict(int)
    diff_stats: dict[str, dict[str, int]] = {
        "easy": {"total": 0, "correct": 0},
        "medium": {"total": 0, "correct": 0},
        "hard": {"total": 0, "correct": 0},
    }
    detailed_mistakes: list[dict[str, Any]] = []

    for ans in answers:
        q = questions.get(ans.question_id)
        if not q:
            continue
        diff_key = q.difficulty if q.difficulty in diff_stats else "medium"
        diff_stats[diff_key]["total"] += 1
        if ans.is_correct:
            diff_stats[diff_key]["correct"] += 1
            continue

        err_cat = ans.error_category or classify_answer_error(
            ans, q, comp_error_counts, q.competency_id in comp_ever_correct
        )
        category_counts[err_cat] += 1
        comp = competencies.get(q.competency_id)
        att = attempt_map.get(ans.attempt_id)

        detailed_mistakes.append({
            "answer_id": ans.id,
            "attempt_id": ans.attempt_id,
            "attempt_title": att.title if att else f"Assessment #{ans.attempt_id}",
            "attempt_date": att.completed_at.isoformat() if att and att.completed_at else None,
            "question_id": q.id,
            "question_prompt": q.prompt,
            "options": q.options,
            "selected_index": ans.selected_index,
            "selected_text": q.options[ans.selected_index] if ans.selected_index is not None and ans.selected_index < len(q.options) else "Unanswered",
            "correct_index": q.correct_index,
            "correct_text": q.options[q.correct_index],
            "explanation": q.explanation,
            "subject_name": subjects[q.subject_id].name if q.subject_id in subjects else q.subject_id,
            "topic_name": q.topic_name,
            "competency_id": q.competency_id,
            "competency_name": comp.name if comp else q.competency_id,
            "difficulty": q.difficulty,
            "time_spent_sec": ans.time_spent_sec,
            "expected_time_sec": q.expected_time_sec,
            "error_category": err_cat,
        })

    difficulty_performance = {}
    for d, st in diff_stats.items():
        difficulty_performance[d] = {
            "total": st["total"],
            "correct": st["correct"],
            "accuracy_percent": round((st["correct"] / max(1, st["total"])) * 100.0, 1) if st["total"] else 0.0,
        }

    repeated_weak = []
    for cid, cnt in sorted(comp_error_counts.items(), key=lambda x: -x[1]):
        if cnt >= 1:
            comp = competencies.get(cid)
            repeated_weak.append({
                "competency_id": cid,
                "competency_name": comp.name if comp else cid,
                "subject_id": comp.subject_id if comp else "",
                "topic_name": comp.topic_name if comp else "",
                "error_count": cnt,
                "is_repeated_pattern": cnt >= 2,
            })

    recommendations: list[str] = []
    if category_counts.get("Repeated Error Pattern", 0) > 0:
        top_rep = repeated_weak[0]["competency_name"] if repeated_weak else "weak topics"
        recommendations.append(
            f"Address repeated errors in {top_rep} via concept review before attempting timed mocks."
        )
    if category_counts.get("Time-Management Difficulty", 0) > 0:
        recommendations.append(
            "Reduce over-time or unanswered questions by running 10-minute timed sprints on weak competencies."
        )
    if category_counts.get("Question Interpretation Difficulty", 0) > 0:
        recommendations.append(
            "Slow down reading on Easy/Moderate statement-based MCQs to eliminate avoidable misreads."
        )
    if category_counts.get("Retention Deficiency", 0) > 0:
        recommendations.append(
            "Schedule spaced retrieval quizzes for previously mastered topics showing recall slippage."
        )
    if not recommendations:
        recommendations.append(
            "Maintain mixed-difficulty revision sets and monitor timing consistency across full-length tests."
        )

    return {
        "has_data": True,
        "total_attempts": len(attempts),
        "total_questions_answered": len(answers),
        "total_mistakes": len(detailed_mistakes),
        "has_only_demo_data": all(a.is_demo_seed for a in attempts),
        "error_category_breakdown": dict(category_counts),
        "difficulty_performance": difficulty_performance,
        "repeated_weak_competencies": repeated_weak[:8],
        "detailed_mistakes": detailed_mistakes[:50],
        "recommendations": recommendations,
    }
