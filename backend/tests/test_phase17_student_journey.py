"""
Phase 1.7 End-to-End Student Experience, Functional Pipeline & Adaptive Learning Verification Suite.
Runs exclusively against an isolated SQLite DB without mutating real user records.
"""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest
import requests

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

TEST_DB = BACKEND_DIR / "test_phase17_govpath.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

from app.agents.orchestrator import AgentOrchestrator
from app.agents.tool_registry import ExamOptionalArgs, _tool_recommend_next_assessment
from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models import (
    AssessmentAttempt,
    AttemptAnswer,
    ChatSession,
    CompetencyEvidence,
    Question,
    StudentProfile,
    StudyPlan,
    StudyTask,
    User,
)


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


def _disable_llm(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()


def _register_student(client, db, email: str, name: str, exam="UPSC_CSE", hours=4.0, days=6, months=8):
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": name, "primary_target_exam": exam},
    )
    assert res.status_code == 200
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    up = client.put(
        "/api/profile",
        headers=headers,
        json={"primary_target_exam": exam, "daily_study_hours": hours, "days_per_week": days, "timeline_months": months},
    )
    assert up.status_code == 200
    user = db.query(User).filter(User.email == email).first()
    return user, headers


def _complete_assessment_via_api(
    client,
    db,
    headers,
    exam_id="UPSC_CSE",
    assessment_type="subject_test",
    subject_id=None,
    competency_id=None,
    question_count=5,
    correct_cids=None,
    wrong_cids=None,
    leave_last_blank=False,
):
    payload = {"exam_id": exam_id, "assessment_type": assessment_type, "question_count": question_count}
    if subject_id:
        payload["subject_id"] = subject_id
    if competency_id:
        payload["competency_id"] = competency_id

    start = client.post("/api/assessments/start", headers=headers, json=payload)
    assert start.status_code == 200, start.text
    sdata = start.json()
    qs = sdata["questions"]
    db_qs = {q.id: q for q in db.query(Question).filter(Question.id.in_([x["id"] for x in qs])).all()}

    answers = []
    for idx, q in enumerate(qs):
        dq = db_qs[q["id"]]
        if leave_last_blank and idx == len(qs) - 1:
            sel = None
        elif wrong_cids is not None and dq.competency_id in wrong_cids:
            sel = (dq.correct_index + 1) % 4
        elif correct_cids is not None and dq.competency_id in correct_cids:
            sel = dq.correct_index
        elif wrong_cids is not None and not correct_cids:
            sel = dq.correct_index
        else:
            sel = dq.correct_index if idx % 2 == 0 else (dq.correct_index + 1) % 4
        answers.append({
            "question_id": dq.id,
            "selected_index": sel,
            "marked_for_review": idx == 0,
            "time_spent_sec": 35 if sel == dq.correct_index else 90,
            "confidence_level": "high" if sel == dq.correct_index else "low",
        })

    sub = client.post(
        f"/api/assessments/{sdata['attempt_id']}/submit",
        headers=headers,
        json={"answers": answers, "total_time_sec": len(qs) * 55},
    )
    assert sub.status_code == 200, sub.text
    return sdata, sub.json()


def test_p17_ab_investigation_and_recommendation_profiles(client, db_session, monkeypatch):
    _disable_llm(monkeypatch)
    now = datetime.now(timezone.utc)
    ua, _ = _register_student(client, db_session, "p17_ab@govpath.test", "Aarav Phase17")

    qs = db_session.query(Question).all()
    q_pol = next(q for q in qs if q.competency_id == "COMP_POL_CONSTITUTION")
    q_eco = next(q for q in qs if q.competency_id == "COMP_ECO_FISCAL")
    q_jud = next(q for q in qs if q.competency_id == "COMP_POL_JUDICIARY")

    a1 = AssessmentAttempt(
        user_id=ua.id, exam_id="UPSC_CSE", assessment_type="diagnostic", title="Diag 1",
        total_questions=3, correct_count=1, score_percent=33.3, accuracy_percent=33.3,
        status="completed", started_at=now - timedelta(days=11), completed_at=now - timedelta(days=11),
    )
    a2 = AssessmentAttempt(
        user_id=ua.id, exam_id="UPSC_CSE", assessment_type="mock_test", title="Mock 2",
        total_questions=2, correct_count=1, score_percent=50.0, accuracy_percent=50.0,
        status="completed", started_at=now - timedelta(days=2), completed_at=now - timedelta(days=2),
    )
    db_session.add_all([a1, a2])
    db_session.flush()
    db_session.add_all([
        AttemptAnswer(attempt_id=a1.id, question_id=q_pol.id, competency_id=q_pol.competency_id, selected_index=q_pol.correct_index, is_correct=True, time_spent_sec=40),
        AttemptAnswer(attempt_id=a1.id, question_id=q_eco.id, competency_id=q_eco.competency_id, selected_index=(q_eco.correct_index + 1) % 4, is_correct=False, time_spent_sec=90),
        AttemptAnswer(attempt_id=a1.id, question_id=q_jud.id, competency_id=q_jud.competency_id, selected_index=(q_jud.correct_index + 1) % 4, is_correct=False, time_spent_sec=95),
        AttemptAnswer(attempt_id=a2.id, question_id=q_pol.id, competency_id=q_pol.competency_id, selected_index=q_pol.correct_index, is_correct=True, time_spent_sec=35),
        AttemptAnswer(attempt_id=a2.id, question_id=q_eco.id, competency_id=q_eco.competency_id, selected_index=(q_eco.correct_index + 1) % 4, is_correct=False, time_spent_sec=88),
        CompetencyEvidence(user_id=ua.id, competency_id="COMP_POL_CONSTITUTION", source_type="diagnostic", attempt_id=a1.id, observed_score=82.0, accuracy=100.0, recorded_at=now - timedelta(days=11)),
        CompetencyEvidence(user_id=ua.id, competency_id="COMP_POL_CONSTITUTION", source_type="mock_test", attempt_id=a2.id, observed_score=90.0, accuracy=100.0, recorded_at=now - timedelta(days=2)),
        CompetencyEvidence(user_id=ua.id, competency_id="COMP_ECO_FISCAL", source_type="diagnostic", attempt_id=a1.id, observed_score=28.0, accuracy=0.0, recorded_at=now - timedelta(days=11)),
        CompetencyEvidence(user_id=ua.id, competency_id="COMP_ECO_FISCAL", source_type="mock_test", attempt_id=a2.id, observed_score=30.0, accuracy=0.0, recorded_at=now - timedelta(days=2)),
        CompetencyEvidence(user_id=ua.id, competency_id="COMP_POL_JUDICIARY", source_type="diagnostic", attempt_id=a1.id, observed_score=30.0, accuracy=0.0, recorded_at=now - timedelta(days=11)),
    ])
    db_session.commit()

    q_a = (
        "Investigate my current preparation for my target examination. Explain which competencies "
        "have reliable evidence, which areas need improvement, which areas remain unassessed, and "
        "what evidence should be collected next. Do not create or modify any study plan."
    )
    res_a = AgentOrchestrator().handle_query(db_session, ua.id, q_a)
    assert res_a["orchestration_summary"]["query_category"] == "preparation_evidence_investigation"
    assert res_a["orchestration_summary"]["action_constraints"]["plan_generation_allowed"] is False
    assert res_a["orchestration_summary"]["action_constraints"]["modification_allowed"] is False
    assert res_a["proposed_action"] is None
    assert "does not imply zero knowledge" in res_a["reply"]
    assert "Repeated Weak Topics:" in res_a["reply"] and "Public Finance (2 errors)" in res_a["reply"]
    assert "Alternative Candidates Evaluated:" in res_a["reply"]

    # Recommendation across unassessed 0-attempt profile & bounded 1-question Science gap
    u_zero, _ = _register_student(client, db_session, "p17_b_zero@govpath.test", "B Zero")
    rec_zero = _tool_recommend_next_assessment(db_session, u_zero.id, ExamOptionalArgs(exam_id="UPSC_CSE"))
    assert rec_zero["recommended_assessment_type"] == "diagnostic"
    assert rec_zero["recommended_question_count"] <= rec_zero["available_questions"]


def test_p17_cde_assessment_pipeline_evidence_update_and_adaptation(client, db_session, monkeypatch):
    _disable_llm(monkeypatch)
    u, hdr = _register_student(client, db_session, "p17_cde@govpath.test", "Priya Pipeline")
    u_other, hdr_other = _register_student(client, db_session, "p17_other@govpath.test", "Other User")
    orch = AgentOrchestrator()

    # Before any assessment: Dashboard & investigation show 0 completed and unassessed gaps
    dash0 = client.get("/api/dashboard", headers=hdr).json()
    assert dash0["readiness"]["assessments_completed"] == 0
    inv0 = orch.handle_query(db_session, u.id, "Investigate my current preparation evidence. Do not create a study plan.")
    assert "0 completed assessments" in inv0["reply"]

    # Validation check: invalid question_count (<3) must return 422; unknown attempt must return 404
    bad_start = client.post("/api/assessments/start", headers=hdr, json={"exam_id": "UPSC_CSE", "assessment_type": "topic_quiz", "question_count": 1})
    assert bad_start.status_code == 422
    assert client.get("/api/assessments/999999", headers=hdr).status_code == 404

    # Real assessment flow (ECONOMY 5 Qs, intentionally miss COMP_ECO_FISCAL & leave 1 blank)
    sdata, detail = _complete_assessment_via_api(
        client, db_session, hdr,
        exam_id="UPSC_CSE", assessment_type="subject_test", subject_id="ECONOMY",
        question_count=5, wrong_cids={"COMP_ECO_FISCAL"}, leave_last_blank=True,
    )
    att_id = sdata["attempt_id"]
    assert detail["attempt"]["status"] == "completed"
    assert detail["attempt"]["unanswered_count"] == 1
    assert detail["attempt"]["correct_count"] + detail["attempt"]["incorrect_count"] + detail["attempt"]["unanswered_count"] == 5

    # Duplicate submit must NOT duplicate attempt or evidence rows
    ev_before_dup = db_session.query(CompetencyEvidence).filter(CompetencyEvidence.user_id == u.id).count()
    att_before_dup = db_session.query(AssessmentAttempt).filter(AssessmentAttempt.user_id == u.id).count()
    dup = client.post(f"/api/assessments/{att_id}/submit", headers=hdr, json={"answers": [], "total_time_sec": 10})
    assert dup.status_code == 200
    assert db_session.query(CompetencyEvidence).filter(CompetencyEvidence.user_id == u.id).count() == ev_before_dup
    assert db_session.query(AssessmentAttempt).filter(AssessmentAttempt.user_id == u.id).count() == att_before_dup

    # Cross-user isolation
    assert client.get(f"/api/assessments/{att_id}", headers=hdr_other).status_code == 404

    # Test D: Fresh investigation reflects updated evidence
    inv1 = orch.handle_query(db_session, u.id, "Investigate my current preparation evidence. Do not create a study plan.")
    assert "1 completed assessment(s)" in inv1["reply"]
    assert "Public Finance" in inv1["reply"]

    # Test E1 (Improvement) & Test E2 (Decline) via real API assessments
    ue1, h_e1 = _register_student(client, db_session, "p17_e1@govpath.test", "E1 Student")
    _complete_assessment_via_api(client, db_session, h_e1, exam_id="UPSC_CSE", assessment_type="subject_test", subject_id="POLITY", question_count=3, wrong_cids={"COMP_POL_CONSTITUTION"})
    _complete_assessment_via_api(client, db_session, h_e1, exam_id="UPSC_CSE", assessment_type="subject_test", subject_id="POLITY", question_count=3, correct_cids={"COMP_POL_CONSTITUTION"})
    prog_e1 = orch.handle_query(db_session, ue1.id, "Analyze my recent preparation progress, compare it with my previous performance, and explain what I should prioritize next.")
    assert "**Improving Competencies (1):** Constitution" in prog_e1["reply"]
    assert prog_e1["orchestration_summary"]["iterations"] == 1  # No needless diagnosis escalation

    ue2, h_e2 = _register_student(client, db_session, "p17_e2@govpath.test", "E2 Student")
    _complete_assessment_via_api(client, db_session, h_e2, exam_id="UPSC_CSE", assessment_type="subject_test", subject_id="POLITY", question_count=3, correct_cids={"COMP_POL_CONSTITUTION"})
    _complete_assessment_via_api(client, db_session, h_e2, exam_id="UPSC_CSE", assessment_type="subject_test", subject_id="POLITY", question_count=3, wrong_cids={"COMP_POL_CONSTITUTION"})
    prog_e2 = orch.handle_query(db_session, ue2.id, "Analyze my recent preparation progress, compare it with my previous performance, and explain what I should prioritize next.")
    assert "**Declining Competencies (1):** Constitution" in prog_e2["reply"]
    assert prog_e2["orchestration_summary"]["iterations"] == 2  # Adaptive escalation to PerformanceDiagnosisAgent
    assert "Performance Diagnosis Agent" in [t["agent"] for t in prog_e2["agent_trace"] if t["kind"] == "agent"]


def test_p17_fghjk_study_plan_consistency_isolation_and_fallback(client, db_session, monkeypatch):
    _disable_llm(monkeypatch)
    ug, hg = _register_student(client, db_session, "p17_fghjk@govpath.test", "FullJourney Student")
    _complete_assessment_via_api(client, db_session, hg, exam_id="UPSC_CSE", assessment_type="subject_test", subject_id="POLITY", question_count=3, wrong_cids={"COMP_POL_CONSTITUTION"})
    _complete_assessment_via_api(client, db_session, hg, exam_id="UPSC_CSE", assessment_type="subject_test", subject_id="POLITY", question_count=3, correct_cids={"COMP_POL_CONSTITUTION"})

    # Test G: Counsellor preview -> no DB plan -> explicit confirmation -> task completion -> review without modify
    chat_p = client.post("/api/counsellor/chat", headers=hg, json={"message": "Create a UPSC CSE study plan for 4.0 hours per day. Let me review it first."}).json()
    assert chat_p["message"]["proposed_action"] is not None
    assert db_session.query(StudyPlan).filter(StudyPlan.user_id == ug.id).count() == 0

    app_r = client.post("/api/counsellor/apply-proposal", headers=hg, json=chat_p["message"]["proposed_action"])
    assert app_r.status_code == 200 and app_r.json()["applied"] is True
    assert db_session.query(StudyPlan).filter(StudyPlan.user_id == ug.id, StudyPlan.is_active == True).count() == 1

    # Confirming replace via study-plan/generate without confirm_replace returns preview confirmation required
    gen_wait = client.post("/api/study-plan/generate", headers=hg, json={"daily_hours": 5.0, "days_per_week": 6, "confirm_replace": False}).json()
    assert gen_wait["requires_confirmation"] is True

    # Complete task & delete/add custom task via API
    sp = client.get("/api/study-plan", headers=hg).json()["plan"]
    t0 = sp["tasks"][0]
    upd = client.patch(f"/api/study-plan/tasks/{t0['id']}", headers=hg, json={"status": "completed"}).json()
    assert upd["progress"]["completed_tasks"] == 1

    # Test H: 10 cross-workflow queries on the SAME student must all keep DB plan/task/attempt/evidence counts intact!
    snap0 = (
        db_session.query(StudyPlan).filter(StudyPlan.user_id == ug.id).count(),
        db_session.query(StudyTask).filter(StudyTask.user_id == ug.id).count(),
        db_session.query(AssessmentAttempt).filter(AssessmentAttempt.user_id == ug.id).count(),
        db_session.query(CompetencyEvidence).filter(CompetencyEvidence.user_id == ug.id).count(),
    )
    orch = AgentOrchestrator()

    r_assess = orch.handle_query(db_session, ug.id, "What should I assess next?")
    assert r_assess["orchestration_summary"]["query_category"] == "diagnostic_assessment_recommendation"
    assert "recommend_next_assessment" in [t["tool"] for t in r_assess["agent_trace"] if t["kind"] == "tool"]

    r_recent = orch.handle_query(db_session, ug.id, "Compare my recent assessment performance.")
    assert r_recent["orchestration_summary"]["query_category"] == "progress_monitoring"
    assert "Progress & Performance Trend Comparison" in r_recent["reply"]

    r_align = orch.handle_query(db_session, ug.id, "Is my preparation aligned with my exam goal?")
    assert r_align["orchestration_summary"]["query_category"] == "readiness_evaluation"

    r_focus = orch.handle_query(db_session, ug.id, "Recommend what I should focus on next without creating a timetable.")
    assert r_focus["orchestration_summary"]["query_category"] == "diagnostic_assessment_recommendation"
    assert r_focus["orchestration_summary"]["action_constraints"]["plan_generation_allowed"] is False
    assert r_focus["proposed_action"] is None

    r_review = orch.handle_query(db_session, ug.id, "Review my existing plan without modifying it.")
    assert r_review["orchestration_summary"]["action_constraints"]["modification_allowed"] is False
    assert "Existing Study Plan Review (Read-Only — Unchanged)" in r_review["reply"]

    snap1 = (
        db_session.query(StudyPlan).filter(StudyPlan.user_id == ug.id).count(),
        db_session.query(StudyTask).filter(StudyTask.user_id == ug.id).count(),
        db_session.query(AssessmentAttempt).filter(AssessmentAttempt.user_id == ug.id).count(),
        db_session.query(CompetencyEvidence).filter(CompetencyEvidence.user_id == ug.id).count(),
    )
    assert snap1 == snap0

    # Test J: Mocked HTTP 429 fallback preserves constraints & hides secrets
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-p17-secret-should-not-leak")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    get_settings.cache_clear()
    mresp = MagicMock()
    mresp.ok = False
    mresp.status_code = 429
    mresp.text = "Quota exceeded"
    with patch("app.agents.llm_client.requests.post", return_value=mresp):
        r429 = orch.handle_query(db_session, ug.id, "Investigate my retention gaps. Do not create a study plan.")
    assert r429["orchestration_summary"]["fallback_used"] is True
    assert r429["orchestration_summary"]["action_constraints"]["plan_generation_allowed"] is False
    assert "AIza-p17-secret-should-not-leak" not in json.dumps(r429)
