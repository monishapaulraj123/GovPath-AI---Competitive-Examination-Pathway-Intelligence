# GovPath AI — Competitive Examination Pathway Intelligence

**An Agentic AI-Based Adaptive Government Examination Readiness, Knowledge Transfer, and Career Pathway Optimization Platform**

GovPath AI helps Indian government examination aspirants (`UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `SSC_CHSL`, `IBPS_PO`, `RRB_NTPC`, `UPSC_CDS`) analyze their real preparation evidence, diagnose answer-level errors, evaluate cross-examination skill transfer, manage spaced-retention queues, and build bounded adaptive study schedules.

---

## Problem Statement

Indian government exam aspirants often prepare across overlapping examinations (such as UPSC CSE, TNPSC Group I, and SSC CGL) without structured visibility into:
- Which competencies are verified by real assessment evidence vs merely unassessed blind spots.
- Which conceptual, timing, retention, or interpretation errors drive score loss.
- How much syllabus knowledge realistically transfers across exams after accounting for required depth differences.
- Whether their daily study hours and timeline are realistically aligned with target competency gaps.

## Solution Overview & Key Features

Instead of a static checklist or single-prompt chatbot, GovPath AI combines **deterministic domain intelligence engines**, a **SQLite/PostgreSQL relational evidence ledger**, a **TF-IDF RAG reference store**, and a **constraint-enforcing multi-agent orchestrator**:
- **6 Specialized Tool-Grounded Agents:**
  - `StudentAnalysisAgent`: Profile, availability constraints, evidence-weighted readiness, competency gaps, retention queue, progress, next assessment recommendation.
  - `ExamIntelligenceAgent`: Verified exam structure, competency requirements, official portal sources, and sanitized TF-IDF RAG retrieval.
  - `PerformanceDiagnosisAgent`: Answer-level mistake classification (`Knowledge Deficiency`, `Retention Deficiency`, `Time-Management Difficulty`, `Question Interpretation Difficulty`, `Application Difficulty`, `Repeated Error Pattern`) consuming shared trend state.
  - `KnowledgeTransferAgent`: Graph-driven cross-exam syllabus overlap vs evidence-weighted transferability and bridge-hour estimation.
  - `PathwayPlanningAgent`: Multi-exam pathway ranking and capacity-vs-workload feasibility simulation.
  - `StudyOptimizationAgent`: Adaptive non-persisted study plan preview generation gated strictly behind workflow action constraints and explicit confirmation.
- **Structured Intent Planner & Bounded Evidence Evaluator:** LLM-assisted structured planning (`gemini-3.1-flash-lite`) paired with a clause-scoped prohibition guardrail (`WorkflowActionConstraints`), deterministic fallback planning, and bounded Iteration 2 follow-up continuation.
- **54-Question Verified Curated Bank:** At least 3 original curated questions across all 18 core competencies (`COMP_POL_*`, `COMP_ECO_*`, `COMP_HIS_*`, `COMP_GEO_*`, `COMP_SCI_GENERAL`, `COMP_CA_POLICY`, `COMP_QNT_*`, `COMP_RSN_ANALYTICAL`, `COMP_ENG_COMPREHENSION`, `COMP_TN_HERITAGE_ADMIN`).
- **Authentic Execution Trace UI:** Displays workflow category, provider vs deterministic fallback status, action restrictions, executed/skipped/failed steps, error disclosures, and RAG citations.

---

## Architecture Diagram

```mermaid
flowchart TD
    UI[React + Vite Frontend] -->|/api REST| API[FastAPI Backend]
    API --> Auth[PBKDF2 + HS256 JWT Security]
    API --> Assess[Assessment & Evidence Pipeline]
    API --> Engines[Readiness, Gap, Retention, Diagnosis, Transfer, Simulator]
    API --> Orch[AgentOrchestrator]

    Orch --> Planner[Structured Intent Planner + Constraint Guardrails]
    Planner -->|Gemini JSON or Deterministic Fallback| Orch
    Orch --> Loop[Bounded Iterative Loop max 4 iters / 24 tools]
    Loop --> Agents[6 Specialized Agents]
    Agents --> Registry[Typed-Schema ToolRegistry + Cache]
    Registry --> Engines
    Registry --> RAG[TF-IDF RAG Store]
    Orch --> Eval[Evidence Evaluator]
    Eval -->|Follow-up needed| Loop
    Orch --> Synth[Grounded Response Synthesizer + Numeric Guardrail]
```

## Workflow Summary

1. **Sanitize & Constrain:** Query is sanitized and scanned for clause-scoped action prohibitions (`do not create/save/modify/activate ... study plan`, `investigation_only`).
2. **Plan:** `plan_user_query` uses Gemini JSON mode (`gemini-3.1-flash-lite`) when configured, falling back deterministically on missing key, `429`, `503`, timeout, or invalid output. `_normalize_plan` enforces all deterministic prohibitions over LLM plans.
3. **Execute & Evaluate:** `AgentOrchestrator` runs only required agents via `ToolRegistry` (typed Pydantic validation, duplicate call caching, cross-user rejection, per-tool timeout). `Evidence Evaluator` checks intermediate findings and conditionally triggers Iteration 2 follow-ups (e.g., escalating to `PerformanceDiagnosisAgent` on declining scores, overdue revisions, or low accuracy).
4. **Synthesize & Guardrail:** `_compose_grounded_reply` compiles tool-backed facts; optional Gemini prose polishing is verified by `_verify_numeric_grounding` (rejecting any ungrounded percentage tokens and reverting cleanly to deterministic grounded output).

---

## Technology Stack

- **Backend:** Python 3.11+, FastAPI `0.115.0`, Uvicorn, SQLAlchemy `>=2.0.35`, Pydantic `2.9.2`, NumPy, scikit-learn (TF-IDF cosine RAG), `python-dotenv`, `requests`.
- **Database:** SQLite (`govpath_ai.db` default with `PRAGMA foreign_keys=ON`) or PostgreSQL via `DATABASE_URL` (`docker-compose.yml` provided).
- **LLM Integration:** Google Gemini API (`gemini-3.1-flash-lite` default via `GEMINI_API_KEY`) with deterministic grounded fallback (`OpenAI` runtime disabled).
- **Frontend:** React 18, TypeScript, Vite 5, Tailwind CSS, React Router, Recharts, Lucide React.
- **Testing:** `pytest` + FastAPI `TestClient` + `unittest.mock`, Playwright Chromium (isolated headless E2E).

---

## Installation & Setup

### 1. Backend Setup
```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
```

### 2. Environment & Gemini Configuration (`backend/.env`)
Configure environment variables in `backend/.env` (never commit `.env` — ignored by `.gitignore`):
- `SECRET_KEY`: Set a strong random signing secret before production deployment.
- `DATABASE_URL`: Defaults to `sqlite:///./govpath_ai.db`. For PostgreSQL, use `postgresql+psycopg2://postgres:postgres@localhost:5432/govpath_ai` (or launch `docker compose up -d`).
- `LLM_PROVIDER`: Set `gemini` (default) or `none` (to run strictly in deterministic fallback mode).
- `GEMINI_API_KEY`: Optional Google AI Studio / Gemini API key. Leave blank to run in Grounded Deterministic Synthesis Mode.
- `GEMINI_MODEL`: Defaults to `gemini-3.1-flash-lite`.
- `CORS_ORIGINS`: Comma-separated allowed origins (e.g. `http://localhost:5173,http://127.0.0.1:5173`).

### 3. Database Setup
No manual migration step is needed for local setup. On startup, FastAPI executes `Base.metadata.create_all(bind=engine)` and idempotent `seed_database(db)`, which creates tables and seeds reference exams, 18 competencies, 54 curated questions, RAG documents, and the `demo@govpath.ai` workspace without overwriting existing user data.

### 4. Frontend Setup
```bash
cd frontend
npm install
```

### 5. Running the Application
Terminal 1 (Backend):
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```
Open `http://localhost:5173`. Click **Enter Demonstration Student Workspace (Arjun Krishnan)** (`demo@govpath.ai`) or switch to **Create Account** to start from a fresh aspirant baseline.

---

## Testing

```bash
# Backend unit, orchestrator, security, question bank & end-to-end tests
cd backend
pytest -v

# Frontend TypeScript & Vite production build check
cd frontend
npm run build
```
See [TESTING.md](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/TESTING.md) for detailed test suites, database isolation, LLM mocking, and Playwright E2E steps.

---

## Deployment Overview

1. Build static frontend assets via `cd frontend && npm run build` (outputs to `frontend/dist`).
2. Configure backend `backend/.env` with `ENVIRONMENT=production`, a strong `SECRET_KEY`, PostgreSQL `DATABASE_URL` (`psycopg2-binary`), explicit `CORS_ORIGINS`, and optional `GEMINI_API_KEY`.
3. Serve `frontend/dist` behind a reverse proxy (Nginx/Caddy) routing `/api/*` to Uvicorn/Gunicorn (`uvicorn app.main:app --host 0.0.0.0 --port 8000`), and verify `GET /api/health` returns `{"status": "ok"}`.

---

## Known Limitations

- **Question Bank Depth:** Curated bank provides 3 verified questions per competency (`54` total) to natively support API/UI quizzes (`>= 3` questions); full-scale exam practice still requires expanding domain-specific banks.
- **Live LLM Quota & Numeric Guardrail:** Live Gemini calls depend on external API quota; on HTTP `429`/`503`/timeout or when Gemini rewrites alter percentage formatting, the system reverts to deterministic grounded output.
- **Reference vs Live Cycle Data:** Exam dates, notification deadlines, vacancies, and cycle cutoffs are not scraped live and carry official-portal verification notices.

For detailed technical architecture and student workflows, see [ARCHITECTURE.md](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/ARCHITECTURE.md), [USER_GUIDE.md](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/USER_GUIDE.md), [FINAL_PROJECT_REPORT.md](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/FINAL_PROJECT_REPORT.md), and [GOVPATH_AI_DEMO_SCRIPT.md](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/docs/GOVPATH_AI_DEMO_SCRIPT.md).
