# GovPath AI — Live Demonstration Script

**Target Audience:** Hackathon Judges, Academic Reviewers, Technical Evaluators, Faculty  
**Estimated Duration:** 6–8 minutes  
**Fallback Resilience:** Works identically with live Gemini (`gemini-3.1-flash-lite`) **or** offline deterministic grounded synthesis (`LLM_PROVIDER=none`) without altering the demonstration flow.

---

## 1. Demo Objective
Demonstrate that GovPath AI is a **tool-grounded, constraint-enforcing multi-agent decision intelligence system**—not a static quiz portal or generic wrapper—by showing live adaptation from zero/partial evidence through assessment completion, error diagnosis, retention tracking, cross-exam knowledge transfer, and confirmable study optimization.

---

## 2. Demo Setup (Fresh Student vs Seeded Demo Account)
- **Recommended Path (Live End-to-End Student Adaptation):**
  1. Launch backend (`uvicorn app.main:app --port 8000`) and frontend (`npm run dev` on `http://localhost:5173`).
  2. Click **Create Account**, register a fresh demo aspirant (e.g., `Aditi Sharma`, `aditi@demo.test`, Password `Password123!`, Primary Target `UPSC Civil Services (CSE)`).
  3. *(Optional Fast Preview):* Alternatively, click **Enter Demonstration Student Workspace (Arjun Krishnan)** for pre-seeded 3-assessment multi-exam data.

---

## 3. Step-by-Step Demonstration Sequence & Narration

### Step 1 — Baseline Honesty (Dashboard `/`)
- **Action:** Inspect Dashboard KPIs right after registering `Aditi Sharma`.
- **Narration:** *"Notice Readiness Index, Coverage, Accuracy, and Retention are all 0.0%. Unlike opaque AI apps that guess a baseline, GovPath AI explicitly discloses zero measured evidence and directs the student to establish a baseline."*

### Step 2 — Preparation Investigation With Strict Action Constraints (`/counsellor`)
- **Exact Query:**
  > `Without creating a study plan, investigate my stored preparation records and explain which evidence is currently available, which competencies have insufficient evidence, and what assessment would be most useful to take next.`
- **Expected Workflow & Agents:**
  - Intent: `preparation_evidence_investigation`
  - Agents: `Student Analysis Agent` (Iteration 1; `Study Optimization Agent` is blocked)
- **What to Highlight on Screen:**
  - Trace badges: workflow pill (`preparation_evidence_investigation`), **Provider / Deterministic Fallback** badge, and **`Restricted: No Plan / Investigation Only`** pill.
  - Zero `Confirm & Apply` plan card appears.
  - Recommends **UPSC_CSE Baseline Diagnostic Assessment** (`diagnostic`, `10` questions).

### Step 3 — Completing a Real Assessment (`/assessments`)
- **Action:** Navigate to **Assessments**, select **Subject Assessment**, choose **Indian Polity & Governance** (or **General Science & Technology** / **5 Questions**), click **Start Assessment**, answer questions (deliberately miss 1–2 items, answer others correctly), and click **Submit Test**.
- **Narration:** *"Upon submission, the scoring engine grades answers, classifies mistakes by error type, persists `CompetencyEvidence` rows linked to this attempt, and displays Competency Impact."*

### Step 4 — Evidence Update & Conditional Multi-Agent Escalation (`/counsellor`)
- **Exact Query:**
  > `Investigate my current preparation for my target examination. Explain which competencies have reliable evidence, which areas need improvement, which areas remain unassessed, and what evidence should be collected next. Do not create or modify any study plan.`
- **Expected Workflow & Agents:**
  - Iteration 1: `Student Analysis Agent` reads updated attempt + new `CompetencyEvidence`.
  - **Evidence Evaluator** sees measured mistakes/accuracy `< 65%` or overdue items and **dynamically triggers Iteration 2: `Performance Diagnosis Agent`**!
  - Expand **View execution trace details** to show `iteration_1_check (followup_required)` → `Performance Diagnosis Agent` → `iteration_2_check (sufficient_evidence)`.

### Step 5 — Cross-Examination Knowledge Transfer (`/counsellor` or `/knowledge-transfer`)
- **Exact Query:**
  > `I am exploring whether the skills I have already developed while preparing for UPSC CSE would be useful for SSC CGL. Investigate the competencies I already have evidence for, identify which ones are shared between these examinations, and determine what additional skills I would need to develop.`
- **What to Highlight:**
  - `Exam Intelligence Agent` + `Knowledge Transfer Agent` (`calculate_transferability`) run cleanly.
  - Explicitly contrasts **Theoretical Structural Syllabus Overlap** vs **Verified Individual Evidence** (`verified_mastery_transfer_percent`) and **Target-Only Skills** so structural overlap is never misrepresented as student mastery.

### Step 6 — Adversarial Constraint & Conflicting Instruction Test (`/counsellor`)
- **Exact Query:**
  > `Analyze my weak competencies and recommend what I should focus on next. Do not create, preview, save, modify or activate any study plan.`
- **What to Highlight:** Multi-verb prohibition is strictly enforced (`plan_generation_allowed=False`); `Study Optimization Agent` never executes.

### Step 7 — Authorized Study Plan Preview & Explicit Confirmation (`/counsellor` → `/study-plan`)
- **Exact Query:**
  > `Create a preparation plan for UPSC CSE based on my current assessment evidence, my available study hours and my competency gaps. I want to review the proposed plan before activating it.`
- **What to Highlight:**
  - Generates an **unpersisted Preview Only** plan (`Saved / Active Plan in DB: None saved or activated yet`).
  - Only when the judge clicks **Confirm & Apply** does GovPath AI save & activate the plan cleanly—then navigate to **Adaptive Study Plan** (`/study-plan`) and mark Day 1's first task **Complete** to watch Progress KPIs update live!
