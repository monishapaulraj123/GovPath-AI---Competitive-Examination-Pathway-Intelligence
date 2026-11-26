"""
Phase 1.8 Final Product Readiness, Question Bank Quality, Security Hardening,
Database Integrity, and End-to-End Student Application Smoke Tests.
"""

from collections import Counter
import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

TEST_DB = BACKEND_DIR / "test_phase18_govpath.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models import (
    AssessmentAttempt,
    Competency,
    CompetencyEvidence,
    Exam,
    Question,
    StudyPlan,
    Subject,
    User,
)
from app.seed import seed_database


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_p18_question_bank_quality_and_idempotent_seed(client, db_session):
    """Every supported competency must have >= 3 curated unique questions with valid explanations and mappings."""
    questions = db_session.query(Question).all()
    competencies = db_session.query(Competency).all()
    valid_exam_ids = {e.id for e in db_session.query(Exam).all()}
    valid_subj_ids = {s.id for s in db_session.query(Subject).all()}
    valid_comp_ids = {c.id for c in competencies}

    assert len(questions) >= 54
    q_ids = [q.id for q in questions]
    prompts = [" ".join(q.prompt.lower().split()) for q in questions]
    assert len(set(q_ids)) == len(q_ids), "Duplicate question IDs detected"
    assert len(set(prompts)) == len(prompts), "Duplicate question prompts detected"

    by_comp = Counter()
    for q in questions:
        assert q.competency_id in valid_comp_ids
        assert q.subject_id in valid_subj_ids
        assert isinstance(q.options, list) and len(q.options) == 4
        assert 0 <= q.correct_index <= 3
        assert len((q.explanation or "").strip()) >= 20
        assert isinstance(q.exam_mappings, list) and len(q.exam_mappings) >= 1
        assert all(eid in valid_exam_ids for eid in q.exam_mappings)
        by_comp[q.competency_id] += 1

    # Every competency must support topic quizzes natively (>= 3 questions)
    for cid in valid_comp_ids:
        assert by_comp[cid] >= 3, f"Competency {cid} has only {by_comp[cid]} questions (<3)"

    # Re-running seed_database must remain strictly idempotent without overwriting existing rows
    count_before = db_session.query(Question).count()
    users_before = db_session.query(User).count()
    seed_database(db_session)
    assert db_session.query(Question).count() == count_before
    assert db_session.query(User).count() == users_before


def test_p18_security_and_database_integrity_hardening(client, db_session):
    # 1. SQLite foreign_keys PRAGMA must be enabled
    fk_val = db_session.execute(text("PRAGMA foreign_keys")).scalar()
    assert fk_val == 1

    # 2. Protected routes enforce authentication
    for route in ["/api/dashboard", "/api/profile", "/api/assessments", "/api/study-plan", "/api/retention", "/api/diagnosis"]:
        r = client.get(route)
        assert r.status_code == 401

    # 3. Malformed JWT must not leak internal parse tracebacks
    bad_jwt = client.get("/api/dashboard", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert bad_jwt.status_code == 401
    assert bad_jwt.json()["detail"] == "Invalid or expired authentication token"

    # 4. Deactivated user cannot log in
    reg = client.post(
        "/api/auth/register",
        json={"email": "p18_deact@govpath.test", "password": "Password123!", "full_name": "Inactive User"},
    )
    assert reg.status_code == 200
    u = db_session.query(User).filter(User.email == "p18_deact@govpath.test").first()
    u.is_active = False
    db_session.commit()
    login_res = client.post("/api/auth/login", json={"email": "p18_deact@govpath.test", "password": "Password123!"})
    assert login_res.status_code == 401

    # 5. CORS must not allow arbitrary untrusted origins with credentials
    cors_res = client.options(
        "/api/health",
        headers={"Origin": "https://evil-untrusted-site.example", "Access-Control-Request-Method": "GET"},
    )
    assert cors_res.headers.get("access-control-allow-origin") != "*"
    assert cors_res.headers.get("access-control-allow-origin") != "https://evil-untrusted-site.example"

    # 6. SQL injection payload in login or RAG search stays safe
    sqli = client.post("/api/auth/login", json={"email": "' OR '1'='1", "password": "Password123!"})
    assert sqli.status_code == 401


def test_p18_end_to_end_application_smoke_journey(client, db_session, monkeypatch):
    """Single coherent 17-step student journey against an isolated account."""
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()

    # 1-2. Register/login & profile exam target
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "p18_smoke@govpath.test",
            "password": "Password123!",
            "full_name": "Smoke Aspirant",
            "primary_target_exam": "UPSC_CSE",
        },
    )
    assert reg.status_code == 200
    hdr = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    u = db_session.query(User).filter(User.email == "p18_smoke@govpath.test").first()

    # 3-7. Baseline investigation without plan creation
    inv1 = client.post(
        "/api/counsellor/chat",
        headers=hdr,
        json={"message": "Investigate my current preparation evidence and tell me what to assess next without creating a study plan."},
    ).json()
    assert inv1["orchestration_summary"]["action_constraints"]["plan_generation_allowed"] is False
    assert "0 completed assessments" in inv1["message"]["content"]
    assert db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id).count() == 0

    # 8-10. Start & complete a 3-question Science & Tech topic assessment cleanly
    start = client.post(
        "/api/assessments/start",
        headers=hdr,
        json={"exam_id": "UPSC_CSE", "assessment_type": "topic_quiz", "competency_id": "COMP_SCI_GENERAL", "question_count": 3},
    ).json()
    assert len(start["questions"]) == 3
    assert all(q["competency_id"] == "COMP_SCI_GENERAL" for q in start["questions"])

    db_qs = {q.id: q for q in db_session.query(Question).filter(Question.id.in_([x["id"] for x in start["questions"]])).all()}
    answers = [{"question_id": q["id"], "selected_index": db_qs[q["id"]].correct_index, "time_spent_sec": 35} for q in start["questions"]]
    sub = client.post(f"/api/assessments/{start['attempt_id']}/submit", headers=hdr, json={"answers": answers, "total_time_sec": 105}).json()
    assert sub["attempt"]["score_percent"] == 100.0
    assert db_session.query(CompetencyEvidence).filter(CompetencyEvidence.user_id == u.id, CompetencyEvidence.competency_id == "COMP_SCI_GENERAL").count() == 1

    # 11-14. Re-investigate & inspect retention/progress
    inv2 = client.post(
        "/api/counsellor/chat",
        headers=hdr,
        json={"message": "How is my preparation progressing now?"},
    ).json()
    assert "1 completed assessment(s)" in inv2["message"]["content"]
    assert client.get("/api/retention", headers=hdr).status_code == 200

    # 15-17. Preview and explicitly confirm study plan, then complete one task
    plan_chat = client.post(
        "/api/counsellor/chat",
        headers=hdr,
        json={"message": "Create a preparation plan for UPSC CSE at 4 hours per day. I want to review it first."},
    ).json()
    prop = plan_chat["message"]["proposed_action"]
    assert prop is not None
    assert db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id).count() == 0

    applied = client.post("/api/counsellor/apply-proposal", headers=hdr, json=prop).json()
    assert applied["applied"] is True
    assert db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id, StudyPlan.is_active == True).count() == 1


def test_p18_question_bank_selection_purity_and_balance(client, db_session):
    """Ensure competency/subject assessments never leak unrelated topics and exam mocks diversify across syllabus."""
    from app.data.exams_seed import COMPETENCIES_SEED, EXAMS_SEED

    reg = client.post(
        "/api/auth/register",
        json={"email": "qbank_purity@govpath.test", "password": "TestPassword@123", "full_name": "QBank Purity"},
    )
    assert reg.status_code == 200
    hdr = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    # 1. Every competency returns 3 pure questions without unrelated padding even when 5 are requested
    for comp in COMPETENCIES_SEED:
        cid = comp["id"]
        exam_id = next(
            (e["id"] for e in EXAMS_SEED if any(r[0] == cid for r in e["competency_requirements"])),
            "UPSC_CSE",
        )
        res = client.post(
            "/api/assessments/start",
            headers=hdr,
            json={"exam_id": exam_id, "assessment_type": "topic_quiz", "competency_id": cid, "question_count": 5},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert len(data["questions"]) == 3
        assert all(q["competency_id"] == cid for q in data["questions"])
        assert all(q["subject_id"] == comp["subject_id"] for q in data["questions"])
        assert data["selection_note"] is not None

    # 2. Subject-restricted tests (including revision mode) never pad from unrelated subjects
    for subj in ["SCIENCE_TECH", "CURRENT_AFFAIRS", "REASONING", "ENGLISH", "STATE_TN"]:
        ex = "TNPSC_GRP1" if subj == "STATE_TN" else ("SSC_CGL" if subj in {"REASONING", "ENGLISH"} else "UPSC_CSE")
        res = client.post(
            "/api/assessments/start",
            headers=hdr,
            json={"exam_id": ex, "assessment_type": "revision", "subject_id": subj, "question_count": 5},
        )
        assert res.status_code == 200
        qs = res.json()["questions"]
        assert len(qs) == 3
        assert all(q["subject_id"] == subj for q in qs)

    # 3. Exam-wide mock distributes across required competencies instead of returning only first two subjects
    upsc_mock = client.post(
        "/api/assessments/start",
        headers=hdr,
        json={"exam_id": "UPSC_CSE", "assessment_type": "mock_test", "question_count": 12},
    ).json()
    assert len({q["competency_id"] for q in upsc_mock["questions"]}) == 12
    assert len({q["subject_id"] for q in upsc_mock["questions"]}) >= 5

    # 4. Unknown filters reject cleanly instead of silent fallback
    bad_comp = client.post(
        "/api/assessments/start",
        headers=hdr,
        json={"exam_id": "UPSC_CSE", "assessment_type": "topic_quiz", "competency_id": "COMP_UNKNOWN", "question_count": 3},
    )
    assert bad_comp.status_code == 400
    bad_subj = client.post(
        "/api/assessments/start",
        headers=hdr,
        json={"exam_id": "UPSC_CSE", "assessment_type": "subject_test", "subject_id": "SUBJ_UNKNOWN", "question_count": 3},
    )
    assert bad_subj.status_code == 400
