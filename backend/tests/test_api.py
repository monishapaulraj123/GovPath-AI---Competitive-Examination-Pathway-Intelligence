import os
import socket
import sys
import threading
import time
from pathlib import Path
import requests
import uvicorn

# Ensure backend root is on sys.path and use isolated test DB
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
TEST_DB = BACKEND_DIR / "test_govpath.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

from app.main import app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_full_govpath_backend_workflow():
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        # Wait for server startup + DB seed
        for _ in range(40):
            try:
                r = requests.get(f"{base}/api/health", timeout=1)
                if r.status_code == 200:
                    break
            except Exception:
                time.sleep(0.15)
        else:
            raise AssertionError("Backend server did not start in time")

        # 1. Health
        res = requests.get(f"{base}/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

        # 2. Demo login & Dashboard
        demo_res = requests.post(f"{base}/api/auth/demo")
        assert demo_res.status_code == 200
        demo_token = demo_res.json()["access_token"]
        demo_headers = {"Authorization": f"Bearer {demo_token}"}

        dash = requests.get(f"{base}/api/dashboard", headers=demo_headers)
        assert dash.status_code == 200
        ddata = dash.json()
        assert ddata["readiness"]["readiness_index"] > 0
        assert len(ddata["gap_overview"]) > 0
        assert ddata["study_activity"]["has_active_plan"] is True

        # 3. Register new isolated user
        reg = requests.post(
            f"{base}/api/auth/register",
            json={
                "email": "priya@govpath.test",
                "password": "StrongPassword123",
                "full_name": "Priya Natarajan",
                "primary_target_exam": "TNPSC_GRP1",
            },
        )
        assert reg.status_code == 200
        user_token = reg.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # Verify user isolation (new user starts with 0 completed assessments)
        user_dash = requests.get(f"{base}/api/dashboard", headers=user_headers).json()
        assert user_dash["readiness"]["assessments_completed"] == 0
        assert user_dash["readiness"]["readiness_index"] == 0.0

        # 4. Update profile
        upd = requests.put(
            f"{base}/api/profile",
            headers=user_headers,
            json={"daily_study_hours": 3.5, "state": "Tamil Nadu", "primary_target_exam": "TNPSC_GRP1"},
        )
        assert upd.status_code == 200
        assert upd.json()["daily_study_hours"] == 3.5

        # 5. Start & Submit Assessment -> updates Readiness, Gap, Diagnosis
        start = requests.post(
            f"{base}/api/assessments/start",
            headers=user_headers,
            json={"exam_id": "TNPSC_GRP1", "assessment_type": "diagnostic", "question_count": 6},
        )
        assert start.status_code == 200
        attempt_id = start.json()["attempt_id"]
        qs = start.json()["questions"]
        assert len(qs) == 6

        answers = [
            {"question_id": q["id"], "selected_index": 1, "time_spent_sec": 45}
            for q in qs
        ]
        sub = requests.post(
            f"{base}/api/assessments/{attempt_id}/submit",
            headers=user_headers,
            json={"answers": answers, "total_time_sec": 270},
        )
        assert sub.status_code == 200
        assert sub.json()["attempt"]["status"] == "completed"

        readiness_after = requests.get(f"{base}/api/readiness?exam_id=TNPSC_GRP1", headers=user_headers).json()
        assert readiness_after["readiness_index"] > 0
        assert readiness_after["assessments_completed"] == 1

        # 6. Knowledge Graph & Exam Comparison & Knowledge Transfer
        kg = requests.get(f"{base}/api/knowledge-graph?exam_id=UPSC_CSE", headers=demo_headers)
        assert kg.status_code == 200
        assert kg.json()["stats"]["competency_count"] >= 10

        cmp_res = requests.get(f"{base}/api/exams/compare?exam_ids=UPSC_CSE,TNPSC_GRP1", headers=demo_headers)
        assert cmp_res.status_code == 200
        assert len(cmp_res.json()["competency_matrix"]) >= 10

        kt = requests.get(
            f"{base}/api/knowledge-transfer?source_exam_id=UPSC_CSE&target_exam_id=TNPSC_GRP1",
            headers=demo_headers,
        )
        assert kt.status_code == 200
        assert kt.json()["structural_overlap_percent"] > 50

        # 7. Study Plan Generation, Task Edit & What-If Simulator
        gen = requests.post(
            f"{base}/api/study-plan/generate",
            headers=user_headers,
            json={"exam_id": "TNPSC_GRP1", "daily_hours": 3.5, "confirm_replace": True},
        )
        assert gen.status_code == 200
        plan = gen.json()["plan"]
        assert len(plan["tasks"]) > 0

        first_task_id = plan["tasks"][0]["id"]
        patch = requests.patch(
            f"{base}/api/study-plan/tasks/{first_task_id}",
            headers=user_headers,
            json={"status": "completed"},
        )
        assert patch.status_code == 200
        assert patch.json()["progress"]["completed_tasks"] == 1

        sim = requests.post(
            f"{base}/api/simulator",
            headers=demo_headers,
            json={
                "target_exam_id": "TNPSC_GRP1",
                "daily_hours": 4.0,
                "days_per_week": 6,
                "duration_months": 6,
                "source_exam_id": "UPSC_CSE",
            },
        )
        assert sim.status_code == 200
        assert sim.json()["baseline_comparison"]["projected_readiness_index"] >= sim.json()["baseline_comparison"]["current_readiness_index"]

        # 8. RAG Ingestion + AI Counsellor Agentic Workflow
        ing = requests.post(
            f"{base}/api/rag/ingest",
            headers=demo_headers,
            json={
                "title": "TNPSC Unit 9 Development Indicators Note",
                "exam_id": "TNPSC_GRP1",
                "source_name": "TN State Planning Commission Summary",
                "content": "Tamil Nadu ranks strongly in social sector infrastructure, industrial corridors, and e-Governance delivery systems relevant for TNPSC Unit 9.",
            },
        )
        assert ing.status_code == 200

        chat = requests.post(
            f"{base}/api/counsellor/chat",
            headers=demo_headers,
            json={"message": "Can my UPSC preparation transfer to TNPSC Group I with 3 hours per day?"},
        )
        assert chat.status_code == 200
        cdata = chat.json()
        assert len(cdata["message"]["agent_trace"]) >= 3
        assert cdata["message"]["proposed_action"] is not None
        assert "Knowledge Transfer" in cdata["message"]["content"]

        # 9. Verify Analytics, Diagnosis, Retention, Practice, Notifications, System Status
        for ep in ["/api/analytics", "/api/diagnosis", "/api/retention", "/api/practice/questions", "/api/notifications", "/api/system/status"]:
            r = requests.get(f"{base}{ep}", headers=demo_headers)
            assert r.status_code == 200, f"Endpoint {ep} failed with {r.status_code}"
    finally:
        server.should_exit = True
        thread.join(timeout=3)
