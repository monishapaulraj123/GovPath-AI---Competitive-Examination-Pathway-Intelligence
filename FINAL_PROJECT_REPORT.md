# GovPath AI — Final Project Report

**Project Title:** GovPath AI — Agentic AI-Based Adaptive Government Examination Readiness, Knowledge Transfer and Career Pathway Optimization System  
**Release Milestone:** Phase 1.8 Final Product Readiness & Project Completion

---

## 1. Abstract

GovPath AI is a multi-agent academic decision-support platform built for Indian government examination aspirants (`UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `SSC_CHSL`, `IBPS_PO`, `RRB_NTPC`, `UPSC_CDS`). Rather than functioning as an unconstrained chatbot or static progress dashboard, GovPath AI integrates six specialized tool-grounded agents coordinated by a bounded, constraint-enforcing orchestrator over deterministic psychometric/computational engines, a relational SQLAlchemy evidence ledger, and a TF-IDF RAG store. An external Gemini runtime (`gemini-3.1-flash-lite`) provides optional structured intent planning and prose polishing under strict numeric-grounding guardrails, while deterministic fallback logic preserves full functionality, action safety, and execution transparency whenever live LLM calls are unavailable or quota-limited.

## 2. Problem Statement & Objectives

Aspirants preparing across multiple central and state competitive examinations frequently suffer from unmeasured blind spots, misdiagnosed recurring errors, poor visibility into syllabus overlap vs actual competency mastery, and unrealistic study schedules. GovPath AI addresses these gaps through the following verified objectives:
1. Measure preparation readiness from dated assessment evidence rather than self-reported guesswork.
2. Distinguish confirmed strengths, repeated errors, declining retention, and unassessed blind spots (`0` evidence never misrepresented as zero knowledge).
3. Quantify both structural syllabus overlap and evidence-weighted knowledge transfer across target exams.
4. Coordinate specialized agents dynamically using explicit workflow action constraints and bounded evidence evaluation.
5. Maintain authentic execution traces and graceful deterministic fallback under API failure conditions.

## 3. Proposed Solution & Existing Limitations

GovPath AI combines deterministic backend engines (`readiness.py`, `gap_analysis.py`, `retention.py`, `diagnosis.py`, `transfer.py`, `knowledge_graph.py`, `planner.py`, `simulator.py`, `rag.py`) with a multi-agent layer (`planner.py`, `orchestrator.py`, `specialized.py`, `tool_registry.py`, `llm_client.py`). Deterministic math computes every numerical index; the orchestrator selects minimal required agents and enforces user prohibitions across planner, orchestrator, tool registry, and proposal validation.

Current honest system limitations:
- Seeded curated question bank contains `54` verified questions (`3` per competency across `18` competencies) — sufficient for API/UI topic quizzes (`>= 3` questions), though smaller than full-length competitive exam archives.
- Official cycle notification dates, vacancies, and cutoffs are not scraped live and carry mandatory official-portal verification notices.
- Live Gemini prose rewriting is constrained by strict percentage grounding; if an LLM rewrite introduces ungrounded `%` tokens, the system reverts cleanly to deterministic grounded prose.

## 4. System Architecture & Technologies

- **Frontend:** React `18`, TypeScript, Vite `5.4`, Tailwind CSS, React Router, Recharts, Lucide React (`2,199` compiled modules).
- **Backend:** Python `3.13`, FastAPI `0.115.0`, Uvicorn `0.30.6`, SQLAlchemy `>=2.0.35`, Pydantic `2.9.2`, NumPy, `scikit-learn` (TF-IDF RAG), `requests`, `python-dotenv`.
- **Database:** SQLite (`govpath_ai.db` with `PRAGMA foreign_keys=ON`) and PostgreSQL-compatible via `DATABASE_URL` (`docker-compose.yml`).
- **LLM Provider:** Google Gemini API (`gemini-3.1-flash-lite` default, with `LLM_PROVIDER=none` deterministic mode; OpenAI runtime disabled).

## 5. Agentic AI Design, Orchestrator & Tool Registry

- **Structured Intent & Constraint Planner (`planner.py`):** Supports both Gemini JSON structured planning (`StructuredPlan` schema) and deterministic rule fallback. `extract_action_constraints` performs clause-scoped negation extraction so multi-verb prohibitions (e.g., `"Do not create, preview, save, modify or activate any study plan"`) and conflicting directives (`"do not want a study plan created. However, generate a timetable"`) cannot be bypassed.
- **Six Specialized Agents (`specialized.py`):**
  1. `StudentAnalysisAgent` — retrieves profile, constraints, weighted readiness, full assessed/missing competency lists, retention status, chronological attempt history, read-only study tasks, and scored assessment candidates.
  2. `ExamIntelligenceAgent` — validates exam frameworks, competency weightages, official sources, and sanitized TF-IDF RAG citations.
  3. `PerformanceDiagnosisAgent` — diagnoses answer-level errors and consumes `StudentAnalysisAgent` retention trends from `OrchestrationState` to exclude `Improving` competencies (`>= 70%`) with 1 old mistake from weak classification.
  4. `KnowledgeTransferAgent` — separates structural syllabus overlap from evidence-backed transferability and bridge effort approximations.
  5. `PathwayPlanningAgent` — scores secondary/backup pathways and runs capacity-vs-workload simulation (`Time-Constrained`, `Balanced`, `Comfortable Cushion`).
  6. `StudyOptimizationAgent` — generates unpersisted weekly schedules strictly when `plan_generation_allowed` and `plan_preview_allowed` are enabled.
- **Orchestrator (`orchestrator.py`) & Evidence Evaluator:** Enforces budget bounds (`4` iterations, `24` tool calls, `6` LLM calls, `45s` timeout), checks prerequisites (`PerformanceDiagnosisAgent` skipped if `0` completed attempts; unsupported exams stopped early), runs `Evidence Evaluator` after Iteration 1 to conditionally escalate Iteration 2 (e.g., triggering `PerformanceDiagnosisAgent` on declining performance, overdue retention, or low accuracy), and attaches full `ToolExecutionRecord` traces.
- **Tool Registry (`tool_registry.py`):** `23` Pydantic-typed tools with cross-user guards, workflow action enforcement on `generate_study_plan_preview`, duplicate call caching, `ThreadPoolExecutor` per-tool timeout, and prompt-injection filtering (`sanitize_untrusted_text`).

## 6. Core Functional Systems

- **RAG Engine (`rag.py`):** Overlapping word-window document chunking with `scikit-learn` TF-IDF cosine retrieval across `RAGDocument` / `RAGChunk`.
- **Database Schema (`models.py`):** 14 SQLAlchemy models enforcing user ownership across profiles, attempts, answers, evidence, plans, tasks, saved questions, notifications, and chat sessions.
- **Competency Analysis & Readiness (`readiness.py`, `gap_analysis.py`):** Source-weighted mastery with 30-day exponential recency scaling, distinct competency coverage, and logarithmic confidence scaling (`1 - exp(-0.48 * n)`).
- **Knowledge Transfer (`transfer.py`, `knowledge_graph.py`):** Maps shared vs target-only competencies (`Fully Transferable`, `Partially Transferable`, `Requires Reinforcement`, `Not Covered`), disclosing structural baseline assumptions transparently when unassessed competencies exist.
- **Assessment System (`assessments.py`, `questions_seed.py`):** `54` verified curated MCQs (`3` per competency across `18` competencies). Tracks selected answers, unanswered items, time spent, per-question `error_category`, and idempotent submission (`completed` re-submissions do not duplicate evidence or attempts).
- **Adaptive Learning, Study Optimization & Progress Monitoring (`retention.py`, `engines/planner.py`):** Dynamically scores competing next assessments across overdue retrieval (`4/7/12`-day mastery intervals), repeated errors, and unassessed weightage; requires explicit confirmation before persisting/activating study plans; tracks chronological attempt trajectories and trend states (`Improving`, `Declining`, `Stable`, `Single Observation`, `Needs Baseline`).

## 7. Security, Testing & Validation Results

- **Security Hardening:** Password hashing with per-user salt + 120,000-round `PBKDF2-HMAC-SHA256`; HS256 JWT verification via `hmac.compare_digest`; strict `is_active` check on login; generic invalid-token messages; strict `CORS_ORIGINS` without credentialed wildcard `*`; `PRAGMA foreign_keys=ON` on SQLite; HTML escaping in `MarkdownProse`; secret redaction in `llm_client.py`.
- **Automated Backend Suite (`pytest -v`):** `41 passed, 0 failed, 0 skipped` covering API workflow, orchestrator, Phase 1.5 post-run fixes, Phase 1.6 cross-workflow & adversarial constraints (`E1`–`E6`), Phase 1.7 real assessment-to-adaptation journeys (`A`–`L`), and Phase 1.8 question bank + security hardening + 17-step smoke test.
- **Frontend Production Build (`npm run build`):** `tsc && vite build` passed (`✓ 2199 modules transformed`).
- **Browser UI E2E Validation:** Executed via isolated Playwright headless Chromium across invalid login error handling, registration (`SSC_CGL`), Dashboard baseline, Assessment launch/completion/breakdown, Dashboard evidence update, Retention, Analytics, Study Plan generation/task completion/replacement guard, AI Counsellor restricted investigation trace + proposal confirmation, mobile (`390×844`) responsive menu, and Sign Out — **0 console errors, 0 page errors, 0 HTTP 5xx errors**.
- **Live Gemini Validation:** Verified single-query live planning with `gemini-3.1-flash-lite` (`planner_mode="llm_structured"`, `llm_calls_used=3`, constraints enforced, numeric guardrail verified).

## 8. Future Enhancements & Conclusion

Potential post-release work outside Phase 1 scope includes expanding domain question banks per exam tier, integrating optional live notification feeds from official portals (`upsc.gov.in`, `tnpsc.gov.in`, `ssc.gov.in`), and running multi-user PostgreSQL load testing.

**Conclusion:** GovPath AI achieves a stable, verified, demonstrable v1.0 completion with end-to-end evidence-driven multi-agent intelligence, verified constraint safety, hardened security/data integrity, and clean fallback resilience.
