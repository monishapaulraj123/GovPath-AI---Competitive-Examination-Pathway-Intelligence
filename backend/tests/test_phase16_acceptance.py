"""
Phase 1.6 Cross-Workflow Agentic Behavior Acceptance & Adversarial Validation Suite.
Runs exclusively against an isolated SQLite database without mutating production/demo records.
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

TEST_DB = BACKEND_DIR / "test_phase16_govpath.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

from app.agents.orchestrator import AgentOrchestrator
from app.agents.planner import build_fallback_plan, extract_action_constraints
from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models import (
    AssessmentAttempt,
    AttemptAnswer,
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


def _create_isolated_user(client, db, email: str, name: str, hours=4.5, days=6, months=10):
    reg = client.post("/api/auth/register", json={"email": email, "password": "Password123!", "full_name": name})
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    u = db.query(User).filter(User.email == email).first()
    prof = db.query(StudentProfile).filter(StudentProfile.user_id == u.id).first()
    if prof:
        prof.primary_target_exam = "UPSC_CSE"
        prof.daily_study_hours = hours
        prof.days_per_week = days
        prof.timeline_months = months
        db.commit()
    return u, {"Authorization": f"Bearer {token}"}


def _seed_partial_upsc(db, user_id: int):
    now = datetime.now(timezone.utc)
    qs = db.query(Question).all()
    pol_q = next(q for q in qs if q.competency_id == "COMP_POL_CONSTITUTION")
    eco_q = next(q for q in qs if q.competency_id == "COMP_ECO_MACRO")
    att = AssessmentAttempt(
        user_id=user_id,
        exam_id="UPSC_CSE",
        assessment_type="diagnostic",
        title="Baseline UPSC Mock",
        total_questions=2,
        correct_count=1,
        score_percent=50.0,
        accuracy_percent=50.0,
        status="completed",
        started_at=now - timedelta(days=10),
        completed_at=now - timedelta(days=10),
    )
    db.add(att)
    db.flush()
    db.add_all([
        AttemptAnswer(attempt_id=att.id, question_id=pol_q.id, competency_id=pol_q.competency_id, selected_index=pol_q.correct_index, is_correct=True, time_spent_sec=40),
        AttemptAnswer(attempt_id=att.id, question_id=eco_q.id, competency_id=eco_q.competency_id, selected_index=(eco_q.correct_index + 1) % 4, is_correct=False, time_spent_sec=95, error_category="Knowledge Deficiency"),
        CompetencyEvidence(user_id=user_id, competency_id=pol_q.competency_id, source_type="diagnostic", attempt_id=att.id, observed_score=85.0, accuracy=100.0, recorded_at=now - timedelta(days=10)),
        CompetencyEvidence(user_id=user_id, competency_id=eco_q.competency_id, source_type="diagnostic", attempt_id=att.id, observed_score=35.0, accuracy=0.0, recorded_at=now - timedelta(days=10)),
    ])
    db.commit()


def _seed_progress_fixture(db, user_id: int):
    now = datetime.now(timezone.utc)
    qs = db.query(Question).all()
    q_pol = next(q for q in qs if q.competency_id == "COMP_POL_CONSTITUTION")
    q_eco_m = next(q for q in qs if q.competency_id == "COMP_ECO_MACRO")
    q_eco_f = next(q for q in qs if q.competency_id == "COMP_ECO_FISCAL")
    q_jud = next(q for q in qs if q.competency_id == "COMP_POL_JUDICIARY")

    att1 = AssessmentAttempt(
        user_id=user_id,
        exam_id="UPSC_CSE",
        assessment_type="diagnostic",
        title="UPSC Diagnostic #1",
        total_questions=4,
        correct_count=2,
        score_percent=50.0,
        accuracy_percent=50.0,
        status="completed",
        started_at=now - timedelta(days=10),
        completed_at=now - timedelta(days=10),
    )
    att2 = AssessmentAttempt(
        user_id=user_id,
        exam_id="UPSC_CSE",
        assessment_type="mock_test",
        title="UPSC Revision Mock #2",
        total_questions=4,
        correct_count=2,
        score_percent=62.5,
        accuracy_percent=50.0,
        status="completed",
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=1),
    )
    db.add_all([att1, att2])
    db.flush()

    db.add_all([
        AttemptAnswer(attempt_id=att1.id, question_id=q_pol.id, competency_id=q_pol.competency_id, selected_index=(q_pol.correct_index + 1) % 4, is_correct=False, time_spent_sec=60),
        AttemptAnswer(attempt_id=att1.id, question_id=q_eco_m.id, competency_id=q_eco_m.competency_id, selected_index=q_eco_m.correct_index, is_correct=True, time_spent_sec=40),
        AttemptAnswer(attempt_id=att1.id, question_id=q_eco_f.id, competency_id=q_eco_f.competency_id, selected_index=(q_eco_f.correct_index + 1) % 4, is_correct=False, time_spent_sec=90),
        AttemptAnswer(attempt_id=att2.id, question_id=q_pol.id, competency_id=q_pol.competency_id, selected_index=q_pol.correct_index, is_correct=True, time_spent_sec=35),
        AttemptAnswer(attempt_id=att2.id, question_id=q_eco_m.id, competency_id=q_eco_m.competency_id, selected_index=(q_eco_m.correct_index + 1) % 4, is_correct=False, time_spent_sec=80),
        AttemptAnswer(attempt_id=att2.id, question_id=q_eco_f.id, competency_id=q_eco_f.competency_id, selected_index=(q_eco_f.correct_index + 1) % 4, is_correct=False, time_spent_sec=85),
        AttemptAnswer(attempt_id=att2.id, question_id=q_jud.id, competency_id=q_jud.competency_id, selected_index=(q_jud.correct_index + 1) % 4, is_correct=False, time_spent_sec=95),
        # Improving: Constitution 45 -> 88
        CompetencyEvidence(user_id=user_id, competency_id="COMP_POL_CONSTITUTION", source_type="diagnostic", attempt_id=att1.id, observed_score=45.0, accuracy=0.0, recorded_at=now - timedelta(days=10)),
        CompetencyEvidence(user_id=user_id, competency_id="COMP_POL_CONSTITUTION", source_type="mock_test", attempt_id=att2.id, observed_score=88.0, accuracy=100.0, recorded_at=now - timedelta(hours=1)),
        # Declining + overdue: Economy Macro 82 -> 45
        CompetencyEvidence(user_id=user_id, competency_id="COMP_ECO_MACRO", source_type="diagnostic", attempt_id=att1.id, observed_score=82.0, accuracy=100.0, recorded_at=now - timedelta(days=10)),
        CompetencyEvidence(user_id=user_id, competency_id="COMP_ECO_MACRO", source_type="mock_test", attempt_id=att2.id, observed_score=45.0, accuracy=0.0, recorded_at=now - timedelta(hours=1)),
        # Stable / Repeated error: Public Finance 30 -> 32
        CompetencyEvidence(user_id=user_id, competency_id="COMP_ECO_FISCAL", source_type="diagnostic", attempt_id=att1.id, observed_score=30.0, accuracy=0.0, recorded_at=now - timedelta(days=10)),
        CompetencyEvidence(user_id=user_id, competency_id="COMP_ECO_FISCAL", source_type="mock_test", attempt_id=att2.id, observed_score=32.0, accuracy=0.0, recorded_at=now - timedelta(hours=1)),
        # Single Observation Overdue: Judiciary 28 from 10 days ago
        CompetencyEvidence(user_id=user_id, competency_id="COMP_POL_JUDICIARY", source_type="diagnostic", attempt_id=att1.id, observed_score=28.0, accuracy=0.0, recorded_at=now - timedelta(days=10)),
    ])

    plan = StudyPlan(
        user_id=user_id,
        exam_id="UPSC_CSE",
        title="Existing Phase 1.6 Plan",
        daily_hours=4.5,
        days_per_week=6,
        is_active=True,
        generation_rationale="Isolated test plan",
    )
    db.add(plan)
    db.flush()
    db.add_all([
        StudyTask(plan_id=plan.id, user_id=user_id, day_index=1, scheduled_date=now.date().isoformat(), title="Revise Judiciary", subject_name="Indian Polity & Governance", topic_name="Judiciary", competency_id="COMP_POL_JUDICIARY", task_type="revision", duration_minutes=45, priority="high", status="completed"),
        StudyTask(plan_id=plan.id, user_id=user_id, day_index=2, scheduled_date=now.date().isoformat(), title="Practice Fiscal Policy", subject_name="Indian Economy & Development", topic_name="Public Finance", competency_id="COMP_ECO_FISCAL", task_type="practice_quiz", duration_minutes=60, priority="high", status="pending"),
    ])
    db.commit()


# ---------------------------------------------------------------------------
# TEST A — COMPETENCY TRANSFER ANALYSIS
# ---------------------------------------------------------------------------

def test_a_competency_transfer_analysis(client, db_session, monkeypatch):
    _disable_llm(monkeypatch)
    u, _ = _create_isolated_user(client, db_session, "p16_testa@govpath.test", "TestA Aspirant")
    _seed_partial_upsc(db_session, u.id)

    plans_before = db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id).count()
    query = (
        "I am exploring whether the skills I have already developed while preparing for UPSC CSE "
        "would be useful for SSC CGL. Investigate the competencies I already have evidence for, "
        "identify which ones are shared between these examinations, and determine what additional "
        "skills I would need to develop."
    )
    res = AgentOrchestrator().handle_query(db_session, u.id, query)
    plans_after = db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id).count()

    s = res["orchestration_summary"]
    executed_agents = [t["agent"] for t in res["agent_trace"] if t["kind"] == "agent" and t["status"] == "completed"]
    executed_tools = [t["tool"] for t in res["agent_trace"] if t["kind"] == "tool" and t["status"] == "completed"]

    assert s["query_category"] == "competency_transfer_analysis"
    assert plans_after == plans_before == 0
    assert res["proposed_action"] is None
    assert "Student Analysis Agent" in executed_agents
    assert "Exam Intelligence Agent" in executed_agents
    assert "Knowledge Transfer Agent" in executed_agents
    assert "Study Optimization Agent" not in executed_agents
    assert "calculate_transferability" in executed_tools
    assert "get_competency_evidence" in executed_tools

    reply = res["reply"]
    assert "Theoretical Structural Syllabus Overlap:" in reply
    assert "Verified Individual Evidence:" in reply
    assert "Money & Banking" in reply
    assert "Constitution" in reply
    assert "Additional Target-Only Skills Needed:" in reply
    assert "StudyOptimizationAgent" not in executed_agents


# ---------------------------------------------------------------------------
# TEST B — PREPARATION FEASIBILITY INVESTIGATION
# ---------------------------------------------------------------------------

def test_b_preparation_feasibility_investigation(client, db_session, monkeypatch):
    _disable_llm(monkeypatch)
    u, _ = _create_isolated_user(client, db_session, "p16_testb@govpath.test", "TestB Aspirant", hours=2.0, days=5, months=3)
    _seed_partial_upsc(db_session, u.id)

    plans_before = db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id).count()
    query = (
        "I am worried that the amount of time I have left is insufficient for my current examination goal. "
        "I do not want a timetable yet. First investigate whether my current preparation is realistically "
        "aligned with my goal and what evidence supports your assessment."
    )
    res = AgentOrchestrator().handle_query(db_session, u.id, query)
    plans_after = db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id).count()

    s = res["orchestration_summary"]
    executed_agents = [t["agent"] for t in res["agent_trace"] if t["kind"] == "agent" and t["status"] == "completed"]
    executed_tools = [t["tool"] for t in res["agent_trace"] if t["kind"] == "tool" and t["status"] == "completed"]

    assert s["query_category"] == "preparation_feasibility_analysis"
    assert s["action_constraints"]["plan_generation_allowed"] is False
    assert s["action_constraints"]["plan_preview_allowed"] is False
    assert s["action_constraints"]["plan_activation_allowed"] is False
    assert plans_after == plans_before == 0
    assert res["proposed_action"] is None
    assert "Study Optimization Agent" not in executed_agents
    assert "generate_study_plan_preview" not in executed_tools
    assert "simulate_preparation_constraints" in executed_tools
    assert "Pathway Planning Agent" in executed_agents

    reply = res["reply"]
    assert "Time-Constrained" in reply
    assert "129.9h available" in reply
    assert "do not represent guaranteed exam outcomes or pass probabilities" in reply


# ---------------------------------------------------------------------------
# TEST C — EXPLICIT STUDY PLAN GENERATION (PREVIEW + EXPLICIT CONFIRMATION)
# ---------------------------------------------------------------------------

def test_c_explicit_study_plan_preview_and_confirmation_flow(client, db_session, monkeypatch):
    _disable_llm(monkeypatch)
    u, headers = _create_isolated_user(client, db_session, "p16_testc@govpath.test", "TestC Aspirant", hours=4.5, days=6, months=10)
    _seed_partial_upsc(db_session, u.id)

    assert db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id).count() == 0

    query = (
        "Create a preparation plan for UPSC CSE based on my current assessment evidence, "
        "my available study hours and my competency gaps. I want to review the proposed plan before activating it."
    )
    chat_res = client.post("/api/counsellor/chat", headers=headers, json={"message": query})
    assert chat_res.status_code == 200
    data = chat_res.json()
    s = data["orchestration_summary"]
    msg = data["message"]
    executed_tools = [t["tool"] for t in msg["agent_trace"] if t["kind"] == "tool" and t["status"] == "completed"]

    assert s["query_category"] == "study_plan_generation"
    assert "generate_study_plan_preview" in executed_tools
    assert msg["proposed_action"] is not None
    assert msg["proposed_action"]["proposal_type"] == "apply_study_plan"

    # Must NOT silently persist or activate during chat
    assert db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id).count() == 0
    assert "Preview Only, Not Saved or Active" in msg["content"]
    assert "Saved / Active Plan in DB: None saved or activated yet." in msg["content"]

    # Explicit confirmation saves & activates exactly 1 plan without duplication
    apply1 = client.post("/api/counsellor/apply-proposal", headers=headers, json=msg["proposed_action"])
    assert apply1.status_code == 200
    assert apply1.json()["applied"] is True
    active_plans = db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id, StudyPlan.is_active == True).all()
    assert len(active_plans) == 1

    # Confirming a second time replaces active plan cleanly without multiple active plans
    apply2 = client.post("/api/counsellor/apply-proposal", headers=headers, json=msg["proposed_action"])
    assert apply2.status_code == 200
    active_plans_after = db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id, StudyPlan.is_active == True).all()
    assert len(active_plans_after) == 1


# ---------------------------------------------------------------------------
# TEST D — PROGRESS MONITORING AND ADAPTIVE RESPONSE
# ---------------------------------------------------------------------------

def test_d_progress_monitoring_and_adaptive_response(client, db_session, monkeypatch):
    _disable_llm(monkeypatch)
    u, _ = _create_isolated_user(client, db_session, "p16_testd@govpath.test", "TestD Aspirant")
    _seed_progress_fixture(db_session, u.id)

    plans_before = [(p.id, p.is_active) for p in db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id).order_by(StudyPlan.id).all()]
    query = (
        "Analyze my recent preparation progress, compare it with my previous performance, "
        "identify whether my preparation is improving or stagnating, and explain what I should prioritize next."
    )
    res = AgentOrchestrator().handle_query(db_session, u.id, query)
    plans_after = [(p.id, p.is_active) for p in db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id).order_by(StudyPlan.id).all()]

    assert plans_after == plans_before
    assert res["proposed_action"] is None

    s = res["orchestration_summary"]
    executed_agents = [t["agent"] for t in res["agent_trace"] if t["kind"] == "agent" and t["status"] == "completed"]
    executed_tools = [t["tool"] for t in res["agent_trace"] if t["kind"] == "tool" and t["status"] == "completed"]

    # Must classify as progress_monitoring and NOT trigger spurious KnowledgeTransferAgent
    assert s["query_category"] == "progress_monitoring"
    assert "Knowledge Transfer Agent" not in executed_agents
    # Evaluator must trigger Iteration 2 PerformanceDiagnosisAgent from intermediate overdue/declining/low-acc findings
    assert s["iterations"] == 2
    assert executed_agents == ["Student Analysis Agent", "Performance Diagnosis Agent"]
    assert "get_retention_status" in executed_tools
    assert "get_preparation_progress" in executed_tools
    assert "recommend_next_assessment" in executed_tools
    assert "diagnose_assessment_errors" in executed_tools

    reply = res["reply"]
    assert "Progress & Performance Trend Comparison" in reply
    assert "+12.5 pts" in reply
    assert "**Improving Competencies (1):** Constitution (45.0% → 88.0%)" in reply
    assert "**Declining Competencies (1):** Money & Banking (82.0% → 45.0%)" in reply
    assert "**Stable Competencies (1):** Public Finance (30.0% → 32.0%)" in reply
    assert "**Insufficient Trend History (1 single-observation, 12 unassessed):**" in reply
    assert "Alternative Priorities Evaluated:" in reply

    # Repeated weak topics must list Public Finance, NOT classify improving Constitution as weak
    diag_section = reply.split("### Performance & Error Diagnosis")[-1]
    assert "Public Finance (2 errors)" in diag_section
    assert "Constitution" not in diag_section.split("Repeated Weak Topics:")[-1].splitlines()[0]

    # Evaluator trace must reflect adaptive followup_required -> sufficient_evidence
    sa_rep = next((a for a in res["agent_trace"] if a["kind"] == "evaluator" and "followup_required" in a["output_summary"]), None)
    assert sa_rep is not None


# ---------------------------------------------------------------------------
# TEST E — ADVERSARIAL ACTION CONSTRAINTS (E1–E6)
# ---------------------------------------------------------------------------

def test_e_adversarial_action_constraints_e1_to_e6(client, db_session, monkeypatch):
    _disable_llm(monkeypatch)
    u, _ = _create_isolated_user(client, db_session, "p16_teste@govpath.test", "TestE Aspirant")
    _seed_progress_fixture(db_session, u.id)
    orch = AgentOrchestrator()

    def plan_snapshot():
        return (
            [(p.id, p.title, p.is_active) for p in db_session.query(StudyPlan).filter(StudyPlan.user_id == u.id).order_by(StudyPlan.id).all()],
            [(t.id, t.status, t.title) for t in db_session.query(StudyTask).filter(StudyTask.user_id == u.id).order_by(StudyTask.id).all()],
        )

    before = plan_snapshot()

    # E1: Multi-verb explicit prohibition
    q_e1 = "Analyze my weak competencies and recommend what I should focus on next. Do not create, preview, save, modify or activate any study plan."
    r_e1 = orch.handle_query(db_session, u.id, q_e1)
    assert r_e1["orchestration_summary"]["action_constraints"]["plan_generation_allowed"] is False
    assert r_e1["orchestration_summary"]["action_constraints"]["plan_preview_allowed"] is False
    assert r_e1["orchestration_summary"]["action_constraints"]["plan_activation_allowed"] is False
    assert r_e1["orchestration_summary"]["action_constraints"]["modification_allowed"] is False
    assert r_e1["proposed_action"] is None
    assert all(t["agent"] != "Study Optimization Agent" for t in r_e1["agent_trace"])
    assert "generate_study_plan_preview" not in [t["tool"] for t in r_e1["agent_trace"]]

    # E2: Conflicting request (prohibition must win and conflict must be disclosed)
    q_e2 = "Analyze my preparation. I do not want a study plan created. However, generate a timetable for the next 30 days."
    r_e2 = orch.handle_query(db_session, u.id, q_e2)
    assert r_e2["orchestration_summary"]["action_constraints"]["plan_generation_allowed"] is False
    assert r_e2["proposed_action"] is None
    assert "Conflicting Request Notice" in r_e2["reply"]
    assert all(t["agent"] != "Study Optimization Agent" for t in r_e2["agent_trace"])

    # E3: Ambiguous action must not authorize plan creation or activation
    q_e3 = "Analyze my preparation and organize my next steps."
    r_e3 = orch.handle_query(db_session, u.id, q_e3)
    assert r_e3["orchestration_summary"]["action_constraints"]["plan_generation_allowed"] is False
    assert r_e3["orchestration_summary"]["action_constraints"]["plan_activation_allowed"] is False
    assert r_e3["proposed_action"] is None

    # E4: Modification prohibition (read-only retrieval & recommendations allowed, mutation blocked)
    q_e4 = "Review my current study plan and identify the improvements you would recommend. Do not change the existing plan."
    r_e4 = orch.handle_query(db_session, u.id, q_e4)
    tools_e4 = [t["tool"] for t in r_e4["agent_trace"] if t["kind"] == "tool" and t["status"] == "completed"]
    assert r_e4["orchestration_summary"]["action_constraints"]["modification_allowed"] is False
    assert r_e4["orchestration_summary"]["action_constraints"]["plan_generation_allowed"] is False
    assert r_e4["proposed_action"] is None
    assert "get_existing_study_tasks" in tools_e4
    assert "Existing Study Plan Review (Read-Only — Unchanged)" in r_e4["reply"]
    assert "Recommended Improvements (Advisory Only):" in r_e4["reply"]

    # E5: Activation prohibition during feasibility evaluation
    q_e5 = "Evaluate my current proposed study plan. I want to see whether it is feasible, but do not activate it."
    r_e5 = orch.handle_query(db_session, u.id, q_e5)
    assert r_e5["orchestration_summary"]["action_constraints"]["plan_activation_allowed"] is False
    assert r_e5["proposed_action"] is None
    assert "simulate_preparation_constraints" in [t["tool"] for t in r_e5["agent_trace"]]

    # E6: Investigation-only constraint propagation across planner -> orchestrator -> ToolRegistry -> proposal builder
    c_e6, _, _ = extract_action_constraints(q_e1)
    assert c_e6.investigation_only is True
    assert plan_snapshot() == before


# ---------------------------------------------------------------------------
# TEST F & G — LLM FAILURE MODES, TRACE AUTHENTICITY & CROSS-WORKFLOW MATRIX
# ---------------------------------------------------------------------------

def test_fg_llm_failures_empty_db_and_trace_authenticity(client, db_session, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-phase16-secret-never-leak")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    get_settings.cache_clear()

    u, _ = _create_isolated_user(client, db_session, "p16_testfg@govpath.test", "TestFG Aspirant")
    _seed_progress_fixture(db_session, u.id)
    orch = AgentOrchestrator()

    def mk_resp(ok=True, code=200, text="{}", body=None):
        r = MagicMock()
        r.ok = ok
        r.status_code = code
        r.text = text
        r.json.return_value = body if body is not None else {
            "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
            "usageMetadata": {"totalTokenCount": 40},
        }
        return r

    # 1. Planner fail cases (429, 503, timeout, malformed JSON, empty candidates) + no secret leak
    for effect in [
        lambda *a, **k: mk_resp(False, 429, '{"error":{"code":429,"message":"Quota exceeded"}}'),
        lambda *a, **k: mk_resp(False, 503, '{"error":{"code":503,"message":"Service unavailable"}}'),
        lambda *a, **k: (_ for _ in ()).throw(requests.Timeout("Request timeout")),
        lambda *a, **k: mk_resp(True, 200, "{broken json"),
        lambda *a, **k: mk_resp(True, 200, body={"candidates": []}),
    ]:
        with patch("app.agents.llm_client.requests.post", side_effect=effect):
            r = orch.handle_query(db_session, u.id, "Analyze weak areas. Do not create a study plan.")
        s = r["orchestration_summary"]
        assert s["fallback_used"] is True
        assert s["planner_mode"] == "deterministic_fallback"
        assert s["synthesis_mode"] == "deterministic_grounded"
        assert s["action_constraints"]["plan_generation_allowed"] is False
        assert "AIza-phase16-secret-never-leak" not in json.dumps(r)
        assert any(t["kind"] == "planner" and t["status"] == "failed" for t in r["agent_trace"])
        assert any(t["kind"] == "planner" and t["tool"] == "deterministic_fallback_planner" and t["status"] == "completed" for t in r["agent_trace"])

    # 2. Planner succeeds, Synthesis fails (HTTP 503) -> honest failed synthesis trace & fallback_used=True
    good_plan = json.dumps({
        "user_objective": "Check readiness",
        "query_category": "readiness_evaluation",
        "primary_examination": "UPSC_CSE",
        "mentioned_examinations": ["UPSC_CSE"],
        "required_agents": ["StudentAnalysisAgent"],
        "required_tools": ["get_student_readiness"],
        "execution_sequence": ["StudentAnalysisAgent"],
    })

    def synth_fail_post(url, headers=None, json=None, timeout=None):
        sys_txt = json["system_instruction"]["parts"][0]["text"]
        if "Structured Intent" in sys_txt:
            return mk_resp(True, 200, good_plan)
        if "Evidence Evaluator" in sys_txt:
            return mk_resp(True, 200, '{"sufficient_evidence": true, "additional_agents": [], "additional_tools": [], "missing_evidence": [], "decision_summary": "ok", "stop_reason": "sufficient"}')
        return mk_resp(False, 503, "Synthesis outage")

    with patch("app.agents.llm_client.requests.post", side_effect=synth_fail_post):
        r_synth_fail = orch.handle_query(db_session, u.id, "Check my readiness.")
    s_sf = r_synth_fail["orchestration_summary"]
    assert s_sf["planner_mode"] == "llm_structured"
    assert s_sf["synthesis_mode"] == "deterministic_grounded"
    assert s_sf["fallback_used"] is True
    assert any(t["kind"] == "synthesizer" and t["status"] == "failed" for t in r_synth_fail["agent_trace"])
    assert any(t["kind"] == "synthesizer" and t["tool"] == "deterministic_grounded_synthesizer" and t["status"] == "completed" for t in r_synth_fail["agent_trace"])

    # 3. Empty DB user with missing profile -> safe recovery, no fabricated assessments
    u_empty = User(email="p16_empty@govpath.test", hashed_password="x", full_name="Empty User")
    db_session.add(u_empty)
    db_session.commit()
    _disable_llm(monkeypatch)
    r_empty = orch.handle_query(db_session, u_empty.id, "Evaluate my preparation progress.")
    assert r_empty["orchestration_summary"]["workflow_status"] == "completed_with_limitations"
    assert "0.0%" in r_empty["reply"]
    assert "Insufficient Evidence" in r_empty["reply"] or "No completed assessments" in r_empty["reply"]
