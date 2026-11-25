# GovPath AI — Government Exam Intelligence

**Agentic AI-Based Adaptive Government Examination Readiness, Knowledge Transfer and Career Pathway Optimization System**

## Architecture Overview

- **Frontend (`frontend/`)**: React 18 + Vite + TypeScript + Tailwind CSS + Recharts + Lucide Icons with a persistent multi-section sidebar workspace.
- **Backend (`backend/`)**: Python + FastAPI + SQLAlchemy (PostgreSQL-ready via `DATABASE_URL`, defaulting to local SQLite for zero-config startup).
- **Core Intelligence Engines (`backend/app/engines/`)**:
  - `knowledge_graph.py`: Structured Exam → Subject → Topic → Competency graph with depth requirements and prerequisite chains.
  - `readiness.py`: Evidence-weighted Student Readiness Model with source weighting, recency decay, and confidence scaling.
  - `gap_analysis.py`: Deterministic Gap Analysis Engine comparing required competency depth vs demonstrated evidence.
  - `transfer.py`: Graph-driven Knowledge Transfer Engine classifying `Fully Transferable`, `Partially Transferable`, `Requires Reinforcement`, and `Not Covered` competencies plus transparent effort approximations.
  - `diagnosis.py`: Rule-based Performance Diagnosis Engine classifying errors (`Knowledge Deficiency`, `Retention Deficiency`, `Question Interpretation Difficulty`, `Time-Management Difficulty`, `Application Difficulty`, `Repeated Error Pattern`).
  - `retention.py`: Observed assessment retention tracking and spaced revision scheduling.
  - `planner.py` & `simulator.py`: AI Pathway Recommendation, Adaptive Study Plan generation, and What-If Scenario Simulation.
  - `rag.py`: Document ingestion, overlapping chunking, TF-IDF cosine retrieval, and verified source attribution.
- **Agentic AI Orchestrator (`backend/app/agents/orchestrator.py`)**:
  - Coordinates 6 specialized tool-grounded agents (`ExamIntelligenceAgent`, `StudentAnalysisAgent`, `PerformanceDiagnosisAgent`, `KnowledgeTransferAgent`, `PathwayPlanningAgent`, `StudyOptimizationAgent`) with optional external LLM synthesis via `OPENAI_API_KEY` or `GEMINI_API_KEY`.

## Quick Start

### 1. Backend
```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Click **Enter Demonstration Student Workspace** to inspect the seeded profile (`demo@govpath.ai`) or register a new account.

### Optional External Databases & LLM Keys
- Configure `DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/govpath_ai` in `backend/.env` (optional `docker compose up -d` provided).
- Set `OPENAI_API_KEY` or `GEMINI_API_KEY` in `backend/.env` to enable external LLM phrasing over the grounded backend outputs. When omitted, GovPath AI operates cleanly in **Grounded Deterministic Synthesis Mode**.
