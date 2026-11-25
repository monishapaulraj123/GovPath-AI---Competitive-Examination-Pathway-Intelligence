"""
Idempotent database seeder for GovPath AI.
Populates verified exam frameworks, competency graph requirements, curated questions,
RAG reference documents, and a clearly labeled Demonstration Student workspace.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.data.exams_seed import COMPETENCIES_SEED, EXAMS_SEED, SUBJECTS_SEED
from app.data.questions_seed import QUESTIONS_SEED
from app.data.rag_seed import RAG_DOCUMENTS_SEED
from app.engines.planner import build_adaptive_study_plan
from app.engines.rag import RAGEngine
from app.models import (
    AssessmentAttempt,
    AttemptAnswer,
    ChatMessage,
    ChatSession,
    Competency,
    CompetencyEvidence,
    Exam,
    ExamCompetencyRequirement,
    Notification,
    Question,
    RAGDocument,
    StudentProfile,
    Subject,
    User,
)
from app.security import hash_password


def seed_database(db: Session) -> None:
    # 1. Subjects
    existing_subjs = {s.id for s in db.query(Subject).all()}
    for s in SUBJECTS_SEED:
        if s["id"] not in existing_subjs:
            db.add(Subject(**s))
    db.flush()

    # 2. Competencies
    existing_comps = {c.id for c in db.query(Competency).all()}
    for c in COMPETENCIES_SEED:
        if c["id"] not in existing_comps:
            db.add(Competency(**c))
    db.flush()

    # 3. Exams & Competency Requirements
    existing_exams = {e.id for e in db.query(Exam).all()}
    for ex in EXAMS_SEED:
        reqs = ex["competency_requirements"]
        ex_payload = {k: v for k, v in ex.items() if k != "competency_requirements"}
        if ex["id"] not in existing_exams:
            db.add(Exam(**ex_payload))
            db.flush()
            for comp_id, depth, weight, label in reqs:
                db.add(
                    ExamCompetencyRequirement(
                        exam_id=ex["id"],
                        competency_id=comp_id,
                        required_depth=float(depth),
                        weightage_percent=float(weight),
                        exam_subject_label=label,
                    )
                )
    db.flush()

    # 4. Curated Question Bank
    existing_qs = {q.id for q in db.query(Question).all()}
    for q in QUESTIONS_SEED:
        if q["id"] not in existing_qs:
            db.add(Question(**q))
    db.flush()

    # 5. RAG Documents
    if db.query(RAGDocument).count() == 0:
        rag = RAGEngine(db)
        for doc in RAG_DOCUMENTS_SEED:
            rag.ingest_document(**doc)

    # 6. Demonstration Student Account (clearly marked is_demo=True & is_demo_seed=True)
    demo_email = "demo@govpath.ai"
    demo_user = db.query(User).filter(User.email == demo_email).first()
    if not demo_user:
        demo_user = User(
            email=demo_email,
            hashed_password=hash_password("DemoPass@123"),
            full_name="Arjun Krishnan",
            is_demo=True,
            is_active=True,
        )
        db.add(demo_user)
        db.flush()

        profile = StudentProfile(
            user_id=demo_user.id,
            display_name="Arjun Krishnan",
            age_range="21-25",
            educational_qualification="B.E. / B.Tech",
            degree_discipline="Computer Science & Engineering",
            graduation_status="Completed",
            state="Tamil Nadu",
            preferred_language="English",
            current_occupation="Full-time Aspirant",
            aspirant_category="graduate",
            daily_study_hours=5.0,
            days_per_week=6,
            timeline_months=10,
            previous_attempts=1,
            previous_experience="Appeared in 1 UPSC Prelims cycle; strong foundational Polity, building Economy & State Unit 8/9.",
            preferred_job_categories=["Civil Services", "State Civil Services", "Staff Selection & Central Group B/C"],
            career_preferences="Administrative & policy leadership roles in Central or Tamil Nadu State services.",
            preferred_exams=["UPSC_CSE", "TNPSC_GRP1", "SSC_CGL"],
            primary_target_exam="UPSC_CSE",
            secondary_target_exams=["TNPSC_GRP1", "SSC_CGL"],
            constraints="Needs structured Current Affairs & Economy revision loops alongside TNPSC backup readiness.",
        )
        db.add(profile)
        db.flush()

        now = datetime.now(timezone.utc)
        # Seed 3 dated demonstration assessments so Readiness, Diagnosis, Retention & Analytics are evidence-backed
        demo_attempts_spec = [
            {
                "days_ago": 18,
                "exam_id": "UPSC_CSE",
                "type": "diagnostic",
                "title": "Demo Diagnostic: UPSC Foundation Baseline",
                "answers": [
                    ("Q_POL_CON_01", 1, 40),
                    ("Q_POL_CON_02", 2, 62),
                    ("Q_POL_PAR_01", 3, 58),
                    ("Q_POL_JUD_01", 0, 52),  # wrong
                    ("Q_ECO_MAC_01", 1, 78),  # wrong + slow
                    ("Q_ECO_FIS_01", 1, 44),
                    ("Q_HIS_MOD_01", 0, 48),
                    ("Q_GEO_PHY_01", 1, 55),
                    ("Q_CA_01", 1, 65),       # wrong
                    ("Q_QNT_ARI_01", 1, 52),
                ],
            },
            {
                "days_ago": 9,
                "exam_id": "UPSC_CSE",
                "type": "subject_test",
                "title": "Demo Subject Test: Economy & Current Affairs",
                "answers": [
                    ("Q_ECO_MAC_01", 0, 56),
                    ("Q_ECO_MAC_02", 0, 82),  # wrong + slow
                    ("Q_ECO_FIS_02", 1, 60),  # wrong
                    ("Q_ECO_GRW_01", 2, 70),  # wrong
                    ("Q_CA_01", 2, 58),       # repeated CA mistake
                    ("Q_CA_02", 1, 42),
                ],
            },
            {
                "days_ago": 3,
                "exam_id": "TNPSC_GRP1",
                "type": "topic_quiz",
                "title": "Demo Cross-Exam Check: Polity, History & TN Heritage",
                "answers": [
                    ("Q_POL_FED_01", 1, 38),
                    ("Q_POL_FED_02", 1, 50),
                    ("Q_HIS_MOD_02", 1, 35),
                    ("Q_HIS_CUL_01", 1, 42),
                    ("Q_GEO_ENV_01", 1, 36),
                    ("Q_SCI_01", 1, 50),
                    ("Q_TN_01", 2, 68),       # wrong
                    ("Q_TN_02", 1, 52),
                ],
            },
        ]

        q_map = {q.id: q for q in db.query(Question).all()}
        for spec in demo_attempts_spec:
            ts = now - timedelta(days=spec["days_ago"])
            q_ids = [a[0] for a in spec["answers"]]
            correct_cnt = 0
            incorrect_cnt = 0
            total_sec = sum(a[2] for a in spec["answers"])

            attempt = AssessmentAttempt(
                user_id=demo_user.id,
                exam_id=spec["exam_id"],
                assessment_type=spec["type"],
                title=spec["title"],
                question_ids=q_ids,
                status="completed",
                total_questions=len(q_ids),
                time_limit_sec=len(q_ids) * 75,
                time_taken_sec=total_sec,
                is_demo_seed=True,
                started_at=ts,
                completed_at=ts,
            )
            db.add(attempt)
            db.flush()

            comp_results: dict[str, list[tuple[bool, int, int]]] = {}
            for qid, sel, sec in spec["answers"]:
                q = q_map[qid]
                is_ok = sel == q.correct_index
                if is_ok:
                    correct_cnt += 1
                else:
                    incorrect_cnt += 1
                err_cat = None if is_ok else ("Time-Management Difficulty" if sec > q.expected_time_sec * 1.25 else "Knowledge Deficiency")
                db.add(
                    AttemptAnswer(
                        attempt_id=attempt.id,
                        question_id=qid,
                        competency_id=q.competency_id,
                        selected_index=sel,
                        is_correct=is_ok,
                        time_spent_sec=sec,
                        error_category=err_cat,
                    )
                )
                comp_results.setdefault(q.competency_id, []).append((is_ok, sec, q.expected_time_sec))

            attempt.correct_count = correct_cnt
            attempt.incorrect_count = incorrect_cnt
            attempt.unanswered_count = 0
            attempt.score_percent = round((correct_cnt / len(q_ids)) * 100.0, 1)
            attempt.accuracy_percent = attempt.score_percent

            for cid, rows in comp_results.items():
                acc = (sum(1 for r in rows if r[0]) / len(rows)) * 100.0
                avg_ratio = sum(min(1.3, r[2] / max(1, r[1])) for r in rows) / len(rows)
                spd = min(100.0, round(avg_ratio * 82.0, 1))
                # Calibrate observed score between 32 and 92
                obs = round(max(30.0, min(92.0, acc * 0.85 + 10.0)), 1)
                db.add(
                    CompetencyEvidence(
                        user_id=demo_user.id,
                        competency_id=cid,
                        source_type=spec["type"],
                        attempt_id=attempt.id,
                        observed_score=obs,
                        accuracy=round(acc, 1),
                        speed_efficiency=spd,
                        weight=1.0,
                        is_demo_seed=True,
                        recorded_at=ts,
                    )
                )

        db.flush()
        # Generate active study plan for demo user and mark first 2 tasks completed
        plan_dict = build_adaptive_study_plan(db, demo_user.id, persist=True)
        if plan_dict and plan_dict.get("tasks"):
            from app.models import StudyTask
            first_two = (
                db.query(StudyTask)
                .filter(StudyTask.user_id == demo_user.id)
                .order_by(StudyTask.id.asc())
                .limit(2)
                .all()
            )
            for t in first_two:
                t.status = "completed"
                t.completed_at = now - timedelta(hours=3)

        # Notifications
        db.add_all([
            Notification(
                user_id=demo_user.id,
                title="High Competency Overlap Detected (UPSC → TNPSC Group I)",
                message="Your Polity and Modern History competencies transfer strongly to TNPSC Group I. Check Knowledge Transfer for Unit 8 & 9 bridge hours.",
                category="insight",
                action_route="/knowledge-transfer",
            ),
            Notification(
                user_id=demo_user.id,
                title="Economy & Current Affairs Gaps Flagged",
                message="Recent demonstration assessment evidence shows gaps in Money & Banking and Current Affairs schemes. Prioritized in your Adaptive Study Plan.",
                category="study_plan",
                action_route="/gap-analysis",
            ),
            Notification(
                user_id=demo_user.id,
                title="Revision Window Due: Constitutional Judiciary",
                message="Last assessed 18 days ago. Schedule a quick 10-minute retrieval check in Practice & Revision.",
                category="revision",
                action_route="/retention",
            ),
        ])

        # Initial AI Counsellor conversation
        sess = ChatSession(user_id=demo_user.id, title="Initial Readiness & Pathway Briefing")
        db.add(sess)
        db.flush()
        db.add(
            ChatMessage(
                session_id=sess.id,
                role="assistant",
                content=(
                    "Welcome to **GovPath AI**, Arjun. I am connected directly to your Readiness Profile, "
                    "Competency Knowledge Graph, Gap Analysis Engine, and verified Exam Reference Base.\n\n"
                    "Based on your demonstration profile targeting **UPSC CSE** (with **TNPSC Group I** and **SSC CGL** as secondary tracks), "
                    "you can ask me to compare exams, calculate preparation transfer, diagnose errors, or adapt your weekly study plan."
                ),
                citations=[],
                agent_trace=[
                    {"agent": "Student Analysis Agent", "tool": "ReadinessModel + GapEngine", "status": "completed"}
                ],
            )
        )
        db.commit()
