# GovPath AI — Phase 1.7 Student Experience, End-to-End Functional Validation & Adaptive Learning Acceptance Report

**Date:** 2026-11-26  
**Milestone:** Phase 1.7 End-to-End Functional & Student-Experience Validation  
**Environment:** FastAPI + SQLAlchemy (isolated SQLite test databases), React + TypeScript + Vite frontend, Gemini `gemini-3.1-flash-lite` + Deterministic Grounded Fallback Runtime

---

## A. Executive Summary

- **What was tested:** End-to-end validation of the actual student journey across registration/profile constraints, dashboard metrics, AI Counsellor preparation investigation, 6 diagnostic assessment-recommendation profiles, live assessment launch/submission/scoring/evidence-persistence pipeline (`/api/assessments/start`, `/api/assessments/{id}/submit`, `/api/assessments/{id}`), immediate competency evidence updates, sequential improvement (E1) and decline (E2) adaptation, spaced-retention tracking & error diagnosis, study plan preview/confirmation/activation/task completion, cross-workflow consistency across 10 student-facing queries (`H1–H10`), database isolation & zero-mutation checks, and LLM failure/guardrail/live-Gemini verification.
- **Overall Acceptance Verdict:** **ACCEPTED WITH LIMITATIONS**
- **Major Findings:**
  1. The end-to-end data pipeline from recommended/started assessment → answer scoring → `AttemptAnswer` & `CompetencyEvidence` persistence → `readiness` / `gap-analysis` / `retention` / `diagnosis` → subsequent AI Counsellor orchestration works reliably on isolated databases without leaking across users or duplicating attempts on repeat submissions.
  2. Cross-workflow consistency probing (`Test H`) exposed **4 intent/tool selection gaps in `planner.py`** for natural student phrasings (`"What should I assess next?"`, `"Compare my recent assessment performance."`, `"Is my preparation aligned with my exam goal?"`, `"Recommend what I should focus on next without creating a timetable."`), which previously fell through to `general_counselling` without invoking `recommend_next_assessment` or chronological progress comparison. All 4 were repaired cleanly.
  3. Frontend static/functional inspection identified **4 genuine UI integration defects** (hardcoded `UPSC_CSE` default exam in `AssessmentsPage.tsx` ignoring user profile target, incomplete exam dropdown options in `AnalyticsPage.tsx`, and missing `try/catch` error surfacing in `StudyPlanPage.tsx` and `CounsellorPage.tsx`). All 4 were repaired and verified with `tsc && vite build`.
  4. A live single-query Gemini check (`gemini-3.1-flash-lite`) succeeded at live `llm_structured` planning (`llm_calls_used=3`, constraints preserved) while the numeric grounding guardrail intentionally reverted Gemini's polished prose because the LLM converted raw required-depth numbers into percentages and added `100.0%` / `90%` not present in grounded output.
- **Remaining Limitations:** Live interactive Chrome browser clicking could not be executed because Chrome remote debugging (`DevToolsActivePort`) was unavailable on the host environment (covered honestly below); seeded single-topic question pools remain small (`1–3` questions per competency vs API `question_count >= 3` and UI `5+` question minimum).

---

## B. Actual Student Journey Validation

Validated flow across implemented backend routes and React pages:

1. **Profile & Goal Setup (`POST /api/auth/register`, `PUT /api/profile`, `DashboardPage.tsx`, `ProfilePage.tsx`)** → **Connected & Verified.** New accounts initialize `0.0%` baseline metrics (`assessments_completed=0`), dashboard displays actionable diagnostic guidance, and `AssessmentsPage.tsx` now reads `primary_target_exam` from `/api/profile`.
2. **Preparation Evidence Investigation (`POST /api/counsellor/chat` / `AgentOrchestrator`, `CounsellorPage.tsx`)** → **Connected & Verified.** Correctly separates demonstrated evidence, insufficient/unassessed competencies (`does not imply zero knowledge`), repeated mistakes, overdue/due-soon retention, and read-only existing plan status while enforcing `plan_generation_allowed=False`.
3. **Diagnostic / Next Assessment Recommendation (`_tool_recommend_next_assessment`)** → **Connected with Question-Pool Constraint Caveat.** Compares overdue retention, repeated mistakes, and unassessed gaps with explicit `priority_score` and `candidate_alternatives`. Limitation: when an isolated unassessed topic has `< 3` questions and no subject fallback (`>= 3`), `StartAssessmentRequest` (`ge=3`) and the UI selector (`5, 8, 12, 15, 25`) pad smaller pools with additional mapped questions at start time.
4. **Assessment Completion & Scoring (`POST /api/assessments/start`, `POST /api/assessments/{id}/submit`, `GET /api/assessments/{id}`)** → **Connected & Verified.** Computes `score_percent`, `accuracy_percent`, unanswered counts, per-answer `error_category`, and writes per-competency `CompetencyEvidence` rows linked cleanly to `user_id`, `attempt_id`, and `competency_id`. Duplicate submissions are idempotent.
5. **Post-Assessment Evidence Update & Adaptive Diagnosis** → **Connected & Verified.** Newly assessed competencies immediately exit missing-evidence lists; E1 improvement updates retention trend to `Improving` (keeping unnecessary `PerformanceDiagnosisAgent` inactive at Iteration 1), whereas E2 decline triggers Iteration 2 escalation to `PerformanceDiagnosisAgent`.
6. **Retention, Study Plan & Progress Monitoring (`/api/retention`, `/api/study-plan`, `PATCH /api/study-plan/tasks/{id}`, `/api/counsellor/apply-proposal`)** → **Connected & Verified.** Study plan previews do not persist until explicit confirmation; task completion updates progress & consistency metrics without fabricating competency mastery.

---

## C. Test Matrix

| Test ID | Scenario | User Query / Action | Expected Behavior | Actual Behavior | Agents Involved | Tools Executed | Database Changes | Test Method | Result | Defect / Repair |
|---|---|---|---|---|---|---|---|---|---|---|
| **A** | Student preparation investigation (mixed evidence + plan) | `"Investigate my current preparation for my target examination... Do not create or modify any study plan."` | Classify investigation; list measured vs unassessed vs repeated weak; no plan changes | Classified `preparation_evidence_investigation`; listed `Judiciary`/`Public Finance`/`Constitution` vs `13` unassessed (`does not imply zero knowledge`); compared 3 next-assessment candidates; blocked plan actions | `StudentAnalysisAgent`, `PerformanceDiagnosisAgent` | `get_aspirant_profile`, `get_preparation_constraints`, `get_student_readiness`, `get_competency_evidence`, `get_retention_status`, `get_preparation_progress`, `recommend_next_assessment`, `diagnose_assessment_errors`, `get_weak_competencies` | `0` plan/task/attempt mutations | Isolated probe + `test_p17_ab_investigation_and_recommendation_profiles` | **PASS** | None needed in Phase 1.7 |
| **B1–B6** | Recommendation across 6 profiles (0-attempt, repeated errors, overdue, improving, declining, 1-Q bank) | `_tool_recommend_next_assessment` across B1–B6 | Appropriate type selection, bounded question count `<= available`, improving not flagged weak | B1 chose `10/24` `diagnostic`; B2/B5 surfaced competing `revision`/`subject_test` candidates with exact error & urgency scores; B6 (`COMP_SCI_GENERAL`) bounded `1/1` without impossible counts | `ToolRegistry` (`recommend_next_assessment`) | `recommend_next_assessment` | Read-only | Isolated probe + `test_p17_ab_investigation_and_recommendation_profiles` | **PASS (with Q-pool caveat)** | Honest Q-count bounds verified; API `ge=3` noted in Section M |
| **C** | Real assessment completion pipeline | `POST /api/assessments/start` (`ECONOMY`, 5 Qs) → `submit` (with 1 blank, wrong `COMP_ECO_FISCAL`) → duplicate `submit` → cross-user `GET` | Score/accuracy accurate, unanswered counted, evidence rows saved once, dup submit idempotent, cross-user `404` | Score `40.0%` (`2/5`), Accuracy `50.0%` (`2/4` answered), Unanswered `1`; `3` `CompetencyEvidence` rows created; dup submit kept `1` attempt & `3` evidence rows; cross-user `404`; `question_count=1` rejected `422` | N/A (REST Assessment Engine) | Assessment router + `classify_answer_error` | Authorized: `+1` `AssessmentAttempt`, `+5` `AttemptAnswer`, `+3` `CompetencyEvidence` | `TestClient` API (`test_p17_cde_assessment_pipeline_evidence_update_and_adaptation`) | **PASS** | None |
| **D** | Competency evidence update immediately post-Test C | `"Investigate my current preparation evidence. Do not create a study plan."` | Assess count increments `0 -> 1`, newly tested competency no longer unassessed, readiness updates | Updated from `0` completed to `1 completed assessment(s)`, `readiness=10.0%`, `18.8%` coverage, `Public Finance` reflected, prior evidence preserved | `StudentAnalysisAgent`, `PerformanceDiagnosisAgent` | Student + Diagnosis read-only tools | `0` mutations | `TestClient` + `AgentOrchestrator` | **PASS** | None |
| **E1** | Sequential improvement (`POLITY` wrong → right on `Constitution`) | Complete 2 real assessments; run progress query | Detects `+66.7 pts` trajectory (`33.3% -> 100.0%`), `Constitution` marked `Improving`, avoids false weak diagnosis | Trajectory `+66.7 pts`; `Improving Competencies (1): Constitution (18.0% -> 98.0%)`; stopped cleanly at Iteration 1 (`PerformanceDiagnosisAgent` not needlessly escalated) | `StudentAnalysisAgent` | 7 student analysis tools incl. `get_retention_status`, `get_preparation_progress` | Authorized `+2` assessment attempts before investigation | `test_p17_cde_assessment_pipeline_evidence_update_and_adaptation` | **PASS** | None |
| **E2** | Sequential decline (`POLITY` right → wrong on `Constitution`) | Complete 2 real assessments (`100% -> 33.3%`); run progress query | Detects decline, triggers diagnosis/retention follow-up | Net `-66.7 pts`; `Declining Competencies (1): Constitution (98.0% -> 18.0%)`; Evaluator escalated to Iteration 2 `PerformanceDiagnosisAgent` (`overdue=1`) | `StudentAnalysisAgent` → `PerformanceDiagnosisAgent` | 9 tools incl. `diagnose_assessment_errors`, `get_weak_competencies` | Authorized `+2` attempts before query | `test_p17_cde_assessment_pipeline_evidence_update_and_adaptation` | **PASS** | None |
| **F** | Retention tracker, error log & task completion distinction | Inspect `/api/retention`, `/api/diagnosis`, complete `StudyTask` | Separates overdue/due-soon/retained/baseline & improving/declining; 14d recency vs tracker distinguished; task completion updates consistency not exam mastery | Retention & recency windows explained separately; task completion updated `completed_tasks=1` (`5.6%`) and surfaced in progress query without faking mastery evidence | `StudentAnalysisAgent` + Retention/Diagnosis engines | `get_retention_status`, `get_preparation_progress` | Authorized `PATCH /study-plan/tasks/{id}` | Probe + `test_p17_fghjk_study_plan_consistency_isolation_and_fallback` | **PASS** | None |
| **G** | Study plan preview → confirmation → activation → task CRUD → replacement guard | Counsellor preview → `apply-proposal` → `/study-plan/generate (confirm_replace=False)` → `PATCH` task → review without modifying | Chat preview saves `0` plans; confirmation saves `1` active plan; unconfirmed replace returns preview; task completion updates metrics; read-only review does not mutate | Chat `proposed_action` returned with `0` DB plans; `apply-proposal` saved `1` active plan; `/study-plan/generate (confirm_replace=False)` returned `requires_confirmation=True`; read-only review preserved DB counts | `StudentAnalysisAgent`, `ExamIntelligenceAgent`, `StudyOptimizationAgent`, `PerformanceDiagnosisAgent` | Includes `generate_study_plan_preview`, `validate_proposed_action`, `get_existing_study_tasks` | Authorized plan save on explicit `apply-proposal`; `0` unplanned writes | `test_p17_fghjk_study_plan_consistency_isolation_and_fallback` | **PASS** | UI error handling improved in `StudyPlanPage.tsx` & `CounsellorPage.tsx` |
| **H1–H10** | Cross-workflow consistency across 10 diverse queries on identical DB state | H1 Evidence, H2 Assess next, H3 Weakest, H4 Compare recent, H5 Retention, H6 Progress, H7 Goal aligned, H8 UPSC→SSC transfer, H9 Review plan, H10 Focus next no timetable | Consistent interpretation across workflows; appropriate intents/tools; zero DB mutations | After repairing H2/H4/H7/H10 in `planner.py`, all 10 queries selected accurate intents (`diagnostic_assessment_recommendation`, `progress_monitoring`, `readiness_evaluation`, etc.), invoked required tools, maintained `mutated=False`, and gave consistent evidence metrics | Varied dynamically per workflow (`1`–`3` agents, `1`–`2` iterations) | Dynamically scoped per intent | `0` mutations across all 10 queries | `run_phase17_probe2.py` + `test_p17_fghjk_study_plan_consistency_isolation_and_fallback` | **PASS (after repair)** | **Repaired:** `planner.py` intent & tool triggers for H2, H4, H7, H10 |
| **I** | Student UI & API integration | Code + Vite build check + attempted browser launch | All routes/pages bind real APIs cleanly without hardcoded wrong targets or silent Promise errors | Repaired hardcoded `UPSC_CSE` target in `AssessmentsPage.tsx`, incomplete exam dropdown in `AnalyticsPage.tsx`, and missing error handling in `StudyPlanPage.tsx` / `CounsellorPage.tsx`; `npm run build` passed. Live Chrome click-through blocked by missing `DevToolsActivePort` | N/A | Static + `tsc && vite build` | None (`browser_e2e.db` cleaned up) | Source audit + build + attempted Chrome subagent | **PARTIAL** | **Repaired:** 4 UI bugs; **Limitation:** Chrome remote debugging unavailable |
| **J** | LLM live, mocked failures & deterministic fallback UX | Live 1-call Gemini check + mocked HTTP 429/503/timeout/malformed JSON/empty + synth fail + tool fail | Live Gemini structured planning works or fails gracefully; fallback preserves constraints, discloses fallback, never leaks secrets | Live `gemini-3.1-flash-lite` succeeded at `llm_structured` planning (`llm_calls_used=3`, `fallback_used=False`, `plan_generation_allowed=False`); numeric grounding guardrail safely rejected ungrounded `%` figures and used `deterministic_grounded` output. Mocked `429`/`503`/timeout/malformed/empty/synth/tool failures all fell back safely with `0` key leaks | Depends on scenario | Verified across planner, evaluator, synthesizer | `0` mutations | `p17_live_orch_once.py` + `test_phase16_acceptance.py` + `test_phase17_student_journey.py` | **PASS** | None |
| **K & L** | Database isolation & student explanation quality | Before/after snapshots across all entities + response usefulness inspection | Ownership enforced across users; zero unintended DB mutations; clear honest limitations | Cross-user isolation (`404`) and strict `snap0 == snap1` verified across investigation/monitoring/review runs; replies clearly distinguish demonstrated scores, `does not imply zero knowledge`, candidate score trade-offs, and read-only plan non-mutation notices | All relevant agents | Full read-only & authorized write paths | Strictly authorized only | Automated DB assertions across suites | **PASS** | None |

---

## D. Student Assessment and Evidence Lifecycle

Verified step by step via live FastAPI `TestClient` against isolated SQLite persistence:
1. **Recommendation → Start:** Student queries readiness/recommendations; `_tool_recommend_next_assessment` evaluates overdue retention, repeated mistakes, and unassessed gaps bounded to actual database question counts. Student calls `POST /api/assessments/start` (`exam_id`, `assessment_type`, optional `subject_id`/`competency_id`, `question_count >= 3`), creating a single `AssessmentAttempt` (`status="in_progress"`).
2. **Submission & Evaluation:** `POST /api/assessments/{attempt_id}/submit` validates ownership (`current_user.id`), iterates over `attempt.question_ids`, scores exact matches (`selected_index == correct_index`), counts unanswered items (`selected_index is None`), computes `score_percent = round((correct / total) * 100.0, 1)` and `accuracy_percent = round((correct / max(1, answered)) * 100.0, 1)`, classifies each wrong/unanswered item via `classify_answer_error` using historical `AttemptAnswer` records, and persists `AttemptAnswer` rows.
3. **Competency Evidence Creation & Idempotency:** Groups answers by `competency_id`, computes speed-blended `observed_score` (`round(min(98.0, max(18.0, acc * 0.85 + spd_eff * 0.15)), 1)`), and creates `CompetencyEvidence` rows with `source_type=attempt.assessment_type` and `attempt_id=attempt.id`. Re-submitting the same `attempt_id` hits `if attempt.status == "completed": return get_assessment_detail(...)`, preventing duplicate attempts or evidence rows.
4. **Reflected Diagnosis:** Subsequent `/api/readiness`, `/api/gap-analysis`, `/api/retention`, and `AgentOrchestrator` calls immediately incorporate the new `CompetencyEvidence` and `AttemptAnswer` rows into weighted readiness (source weight × exponential recency decay), distinct coverage, error logs, and `Competency` evidence counts.

---

## E. Adaptive Behavior Verification

1. **Pre- vs Post-Assessment Adaptation (Test C → D):** Before any attempt, the student received `0.0%` baseline metrics (`0 completed assessments`) and a `10`-question baseline Diagnostic recommendation (`recommended_question_count=10 <= available=24`). After submitting a 5-question `ECONOMY` subject test (`2` correct, `2` incorrect in `COMP_ECO_FISCAL`, `1` unanswered), readiness updated immediately to `10.0%`, distinct coverage to `18.8%`, `Public Finance` moved into recorded evidence (`1 observation`), and `PerformanceDiagnosisAgent` activated automatically in follow-up investigations.
2. **Improvement Adaptation (Test E1):** When the student progressed from `33.3%` (`Constitution` incorrect, `18.0%` score) to `100.0%` (`Constitution` correct, `98.0%` score), `progress_monitoring` surfaced `+66.7 pts` net score growth, labeled `Constitution (18.0% → 98.0%)` as **`Improving`**, omitted it from weak-topic remediation, and terminated cleanly at Iteration `1` (`PerformanceDiagnosisAgent` not unnecessarily triggered).
3. **Decline Adaptation (Test E2):** Reversing the sequence (`100.0%` → `33.3%`, `Constitution 98.0% → 18.0%`) produced `-66.7 pts`, flagged `Constitution` as **`Declining`** and `Revision Overdue`, and caused the `Evidence Evaluator` to dynamically escalate to Iteration `2` (`PerformanceDiagnosisAgent`) to inspect answer-level errors (`diagnose_assessment_errors`).

---

## F. Retention and Progress Validation

- Verified **Retention Tracker (`compute_retention_tracker`)** classifies:
  - `Improving`: delta `>= +5.0` between last two dated observations.
  - `Declining`: delta `<= -5.0` → immediately flagged `Revision Overdue`.
  - `Stable`: delta within `(-5.0, +5.0)`.
  - `Single Observation`: `1` observation (interval-based `Revision Overdue` if `overdue_days >= 3` against `4/7/12`-day mastery intervals, else `Due Soon` / `Retained`).
  - `Needs Baseline` (`Baseline Needed`): `0` observations (`current_estimate=0.0`, no trend fabricated).
- Verified clear separation between **`14-Day Recency Retention` (`readiness.retention_index`)** (percentage of exam target competencies assessed within 14 days) and **Retention Tracker overdue/due-soon counts** (`4/7/12`-day mastery-scaled intervals & declining-score triggers).
- Verified completing a `StudyTask` (`PATCH /api/study-plan/tasks/{id}`) updates `completed_tasks`, `completed_hours`, and `readiness.consistency` cleanly **without** fabricating exam `CompetencyEvidence`.

---

## G. Study Plan Lifecycle

- **Counsellor Preview:** Asking `"Create a preparation plan for UPSC CSE ... review before activating"` runs `StudyOptimizationAgent` (`generate_study_plan_preview`, `persist=False`), writes `0` database `StudyPlan` rows, explicitly labels the plan `Preview Only, Not Saved or Active` alongside `Saved / Active Plan in DB`, and attaches a `Confirm & Apply` `proposed_action`.
- **Confirmation & Idempotency:** Submitting `/api/counsellor/apply-proposal` calls `build_adaptive_study_plan(..., persist=True)`, deactivating any prior active plan and creating `1` active plan (`18` tasks). Repeat confirmation cleanly replaces without creating multiple `is_active=True` plans.
- **UI Manual Generate/Replace Guard:** `POST /api/study-plan/generate` checks for an existing active plan and returns `requires_confirmation=True` + `preview_plan` unless `confirm_replace=True`.
- **Task Progress & Read-Only Constraints:** Completing tasks via `PATCH /api/study-plan/tasks/{id}` updates dashboard/study-plan/analytics progress immediately; adversarial prohibitions (single-verb, multi-verb E1, conflicting E2, ambiguous E3, modification-prohibited E4, activation-prohibited E5) all block unauthorized writes and leave existing DB plans/tasks strictly untouched.

---

## H. UI & API Findings

- **Validated via Backend `TestClient` + Frontend TypeScript/Vite Production Build (`tsc && vite build`):**
  - All student API endpoints (`/auth/*`, `/profile`, `/dashboard`, `/assessments/*`, `/readiness`, `/gap-analysis`, `/knowledge-transfer`, `/diagnosis`, `/retention`, `/analytics`, `/pathways`, `/study-plan*`, `/simulator`, `/counsellor/*`) align with [client.ts](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/frontend/src/api/client.ts).
  - **Defects found & repaired during UI inspection:**
    1. [AssessmentsPage.tsx](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/frontend/src/pages/AssessmentsPage.tsx): Previously hardcoded initial `examId = 'UPSC_CSE'`, ignoring non-UPSC students' saved `primary_target_exam`. Repaired to fetch `api.getProfile()` on load and initialize `examId` to `prof.primary_target_exam`.
    2. [AnalyticsPage.tsx](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/frontend/src/pages/AnalyticsPage.tsx): Exam dropdown omitted `SSC_CHSL`, `RRB_NTPC`, and `UPSC_CDS`. Added all 8 supported exams consistently.
    3. [StudyPlanPage.tsx](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/frontend/src/pages/StudyPlanPage.tsx) and [CounsellorPage.tsx](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/frontend/src/pages/CounsellorPage.tsx): Added `try/catch` error handling around task status/add/delete mutations and proposal application so backend errors render clearly to the student instead of failing silently.
- **Unvalidated Interactive UI Area:** Live Chrome DevTools browser automation could not connect (`Could not find DevToolsActivePort`), so live mouse/DOM click rendering in Chrome was **not** executed in this run and remains documented as an environmental limitation.

---

## I. LLM & Deterministic Fallback Validation

- **Live Gemini Validation (1 bounded isolated test run, `p17_live_orch_once.py`):**
  - `get_llm_status()` reported `configured=True`, `provider="gemini"`, `model="gemini-3.1-flash-lite"`, `openai_active=False`.
  - Orchestrated query `"Investigate my current preparation evidence and tell me what to assess next without creating any study plan."` executed against live `gemini-3.1-flash-lite`:
    - `planner_mode="llm_structured"` (`planner_provider="gemini:gemini-3.1-flash-lite"`), `llm_calls_used=3`, `fallback_used=False`, `llm_error=None`.
    - Enforced `plan_generation_allowed=False`, `investigation_only=True`, `proposed_action=None`.
    - Notably, the numeric grounding guardrail (`_verify_numeric_grounding`) rejected Gemini's response rewrite due to ungrounded percentages (`{'85.0%', '90%', '88.0%', '100.0%', '82.0%', '84.0%'}`) and safely returned `deterministic_grounded` output (`GovPath Grounded Synthesis Engine`) — demonstrating working anti-hallucination protection.
- **Mocked LLM Failure Validation:** Verified HTTP `429`, HTTP `503`, `requests.Timeout`, malformed JSON, empty `candidates`, invalid agent/tool planner output, synthesis HTTP `503` outage, and simulated DB tool crashes all record accurate `failed` + fallback `completed` trace entries, disclose limitations, preserve action constraints, and leak zero secrets.
- **Deterministic Fallback Mode (`LLM_PROVIDER="none"`):** Used for full `38`-test pytest suite and `Test A–H` probes to preserve API quota while deterministically verifying planner constraints, tool routing, adaptive evaluator follow-ups, and grounded synthesis.

---

## J. Data Integrity & Isolation

- **Test Databases Used:** Ephemeral SQLite files (`test_phase17_govpath.db`, `test_phase16_govpath.db`, `test_phase1_govpath.db`, `test_govpath.db`) and isolated scratch DB copies (`phase17_probe.db`, `phase17_probe2.db`, `p17_live_check.db`). Real [govpath_ai.db](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/backend/govpath_ai.db) records were never targeted by test mutations.
- **Verified Constraints & Ownership:** Cross-user assessment detail (`GET /api/assessments/{id}`) and cross-user chat sessions return `404`; cross-user `user_id` tool arguments are rejected by `ToolRegistry`; duplicate assessment submission creates `0` duplicate `AssessmentAttempt` or `CompetencyEvidence` rows.
- **Before/After DB Snapshots:** All read-only queries (`Test A`, `Test B`, `Test D`, `Test H1–H10`, `Test E1–E6`, and pre-confirmation `Test G` chat) produced identical `StudyPlan`, `StudyTask`, `AssessmentAttempt`, and `CompetencyEvidence` counts before and after execution.
- **Cleanup Status:** All ephemeral `test_*.db` and scratch `.db` files were removed after test execution; temporary server daemons were terminated.

---

## K. Regression Results

- **Backend Test Suite (`pytest -v` in `backend/`):** **38 passed, 0 failed, 0 skipped** (`25.61s` / `79.52s` final full run covering Phase 1, Phase 1.5, Phase 1.6, and Phase 1.7 suites):
  - [test_api.py](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/backend/tests/test_api.py): `1` passed
  - [test_orchestrator_phase1.py](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/backend/tests/test_orchestrator_phase1.py): `28` passed
  - [test_phase16_acceptance.py](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/backend/tests/test_phase16_acceptance.py): `6` passed
  - [test_phase17_student_journey.py](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/backend/tests/test_phase17_student_journey.py): `3` passed (`test_p17_ab_investigation_and_recommendation_profiles`, `test_p17_cde_assessment_pipeline_evidence_update_and_adaptation`, `test_p17_fghjk_study_plan_consistency_isolation_and_fallback`)
- **Frontend Production Build (`npm run build` / `tsc && vite build` in `frontend/`):** **Exited with code 0** (`✓ 2199 modules transformed`, `✓ built in 21.10s`).
- **Testing Limitation:** Interactive Chrome DOM run blocked by missing Chrome DevTools remote debugging port.

---

## L. Defects Discovered & Repairs Implemented

1. **Natural Student Phrasing Gaps in Cross-Workflow Intent Routing (`planner.py`)**
   - **Root Cause:** Fallback planner lacked patterns for `"what should i assess"`, `"assess next"`, `"focus on next"`, `"recent assessment performance"`, `"aligned with my exam goal"`, and allowed `"compare"` inside `"Compare my recent assessment performance"` to miss `progress_monitoring`.
   - **Impact:** H2 (`What should I assess next?`), H4 (`Compare my recent assessment performance.`), H7 (`Is my preparation aligned with my exam goal?`), and H10 (`Recommend what I should focus on next without creating a timetable.`) routed to `general_counselling` without running `recommend_next_assessment` or chronological progress trends.
   - **Files Changed:** [planner.py](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/backend/app/agents/planner.py)
   - **Repair:** Added exact intent triggers while guarding inter-exam `wants_compare` when `wants_progress` is active and avoiding double-classification against `wants_diagnosis`/`wants_progress`.
   - **Regression Test:** `test_p17_fghjk_study_plan_consistency_isolation_and_fallback` (`H` assertions in [test_phase17_student_journey.py](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/backend/tests/test_phase17_student_journey.py)).

2. **Hardcoded `UPSC_CSE` Assessment Default & Missing UI Exam/Error Handling (`AssessmentsPage.tsx`, `AnalyticsPage.tsx`, `StudyPlanPage.tsx`, `CounsellorPage.tsx`)**
   - **Root Cause:** `AssessmentsPage` initialized `examId` statically to `'UPSC_CSE'` without consulting `api.getProfile()`; `AnalyticsPage` exam `<select>` omitted 3 of 8 supported exams (`SSC_CHSL`, `RRB_NTPC`, `UPSC_CDS`); async handlers in `StudyPlanPage` and `CounsellorPage` omitted `try/catch` error surfacing.
   - **Impact:** Non-UPSC aspirants saw `UPSC_CSE` selected by default on `/assessments`, `SSC_CHSL`/`RRB_NTPC`/`UPSC_CDS` targets could not be cleanly switched in `/analytics`, and failed plan/proposal mutations failed silently in UI.
   - **Files Changed:** [AssessmentsPage.tsx](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/frontend/src/pages/AssessmentsPage.tsx), [AnalyticsPage.tsx](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/frontend/src/pages/AnalyticsPage.tsx), [StudyPlanPage.tsx](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/frontend/src/pages/StudyPlanPage.tsx), [CounsellorPage.tsx](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/frontend/src/pages/CounsellorPage.tsx).
   - **Verification:** `tsc && vite build` passed with exit code `0`.

---

## M. Remaining Limitations

1. **Question-Bank Coverage vs Minimum Quiz Length:** Several single competencies in [questions_seed.py](file:///d:/GovPath-AI---Competitive-Examination-Pathway-Intelligence/backend/app/data/questions_seed.py) still have `1–2` seeded questions (`COMP_ECO_GROWTH=1`, `COMP_SCI_GENERAL=1`, `COMP_CA_POLICY=2`), whereas `StartAssessmentRequest.question_count` enforces `ge=3` and UI options start at `5`. When a student starts a quiz on a sparse pool, `assessments.py` supplements the selection with additional mapped questions at quiz start time.
2. **LLM Grounding Strictness on Live Gemini Rewrites:** In the observed live Gemini run, `_verify_numeric_grounding` rejected `gemini-3.1-flash-lite`'s prose polish because Gemini appended `%` signs to raw depth values (`85.0` → `85.0%`) and added `100.0%` / `90%`. The guardrail prevented ungrounded figures cleanly by reverting to the deterministic grounded response, though live LLM prose polishing only applies when Gemini avoids introducing ungrounded percentage tokens.
3. **Gemini API Quota / Latency Dependency:** Live Gemini structured planning (`~2.8s`–multi-second latency) remains subject to external quota; deterministic fallback covers all offline/quota-exhausted workflows.
4. **Live Browser Automation Availability:** Interactive Chrome browser click testing could not run because `DevToolsActivePort` was unavailable in the local Chrome profile during this session; frontend correctness was verified via static audit, TypeScript compilation, Vite bundle build, and full backend API contract testing.

---

## N. Phase 1.7 Acceptance Decision

**ACCEPTED WITH LIMITATIONS.**

Across end-to-end student journey verification, the existing GovPath AI backend engines, assessment completion & competency evidence update pipeline, sequential adaptation to improvement and decline, spaced-retention differentiation, study plan preview/confirmation/activation workflow, adversarial action constraints, cross-workflow consistency, and database isolation operate cohesively and accurately (`38/38` backend tests passing, clean frontend `tsc && vite build`, verified live `gemini-3.1-flash-lite` structured planning + safety guardrail). Acceptance is qualified by the documented question-bank sparsity (`1–2` questions on some competencies), strict numeric guardrail reversion during live LLM prose rewriting, and the unavailability of Chrome remote debugging for interactive browser click-through verification.
