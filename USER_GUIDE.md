# GovPath AI — Student User Guide

Welcome to GovPath AI. This guide walks through the actual workflows available in the application.

---

## 1. Logging In & Setting Up Your Profile

- Open GovPath AI (`http://localhost:5173`).
- Choose **Enter Demonstration Student Workspace (Arjun Krishnan)** to explore pre-seeded assessment history, knowledge transfer, retention schedules, and study tasks—or select **Create Account** to register your own aspirant account with your **Primary Target Examination** (`UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `SSC_CHSL`, `IBPS_PO`, `RRB_NTPC`, `UPSC_CDS`).
- Visit **My Profile** (`/profile`) anytime to update your daily study hours, study days per week, target timeline (months), secondary exams, and preparation notes.

---

## 2. Preparation Investigation (Using AI Counsellor)

1. Navigate to **AI Counsellor** (`/counsellor`).
2. To inspect stored evidence without creating or modifying a schedule, ask for example:
   - `"Investigate my current preparation for my target examination. Explain which competencies have reliable evidence, which areas need improvement, which areas remain unassessed, and what evidence should be collected next. Do not create or modify any study plan."`
3. Read each section carefully:
   - **Verified Assessment Evidence:** Shows completed assessments, evidence-weighted Readiness Alignment, Distinct Competency Coverage, Mean Accuracy, and both **14-Day Recency Retention** and **Retention Tracker** overdue counts.
   - **Competencies With Recorded Evidence / Missing Evidence:** Unassessed competencies show `0 evidence records` and explicitly note that missing evidence *does not imply zero real-world knowledge*.
   - **Most Useful Next Assessment:** Compares competing candidates (overdue spaced retrieval, repeated-error remediation, or high-weightage unassessed topics) with priority scores and matching question counts.
   - **Agent Orchestrator Trace:** Below the response, check whether the request used live Gemini (`Provider: gemini`) or **Deterministic Fallback**, confirm active restrictions (`Restricted: No Plan / Investigation Only`), and expand **View execution trace details** to see every executed/skipped step and rationale.

---

## 3. Taking Assessments & Viewing Results

1. Open **Assessments** (`/assessments`) or **Mock Tests** (`/mock-tests`). Your target exam is pre-filled from your profile.
2. Select **Assessment Type** (`Diagnostic Baseline`, `Topic Quiz`, `Subject Assessment`, `Timed Mock Test`, `Spaced Revision Check`), optional **Subject Focus**, and **Questions** (`5`–`25`), then click **Start Assessment**.
3. Use the question navigator on the right to move between questions, **Mark for Review**, **Clear Response**, and track the countdown timer.
4. Click **Submit Test** to immediately view:
   - **Score**, **Correct**, **Incorrect**, **Accuracy**, and **Time Taken**.
   - **Topic Performance** and **Competency Impact**.
   - **Question-Level Review & Explanations**, including assigned error categories (`Knowledge Deficiency`, `Time-Management Difficulty`, `Question Interpretation Difficulty`, `Application Difficulty`, `Retention Deficiency`, `Repeated Error Pattern`).
5. Completed assessments are stored in **Assessment History** (click **Review** anytime) and immediately update **Dashboard**, **Readiness Profile**, **Gap Analysis**, **Retention Tracker**, **Error Analysis**, and **AI Counsellor** evidence.

---

## 4. Progress, Analytics, Retention & Knowledge Transfer

- **Readiness Profile (`/readiness`) & Gap Analysis (`/gap-analysis`):** Switch between supported exams to inspect subject depth vs measured score and prioritized intervention gaps.
- **Performance Analytics (`/analytics`):** Inspect chronological Assessment Score & Accuracy trends, study hours completed vs planned, and subject bar charts.
- **Retention Tracker (`/retention`):** View `Revision Overdue`, `Due Soon`, `Retained`, and `Baseline Needed` competencies along with observed trends (`Improving`, `Declining`, `Stable`, `Single Observation`, `Needs Baseline`).
- **Error Analysis (`/error-analysis`) & Practice (`/practice`):** Filter missed questions (`Incorrect Reattempts`, `Weak Competencies`, `Saved Questions`) and review explanations.
- **Knowledge Transfer (`/knowledge-transfer`) & Simulator (`/simulator`):** Inspect syllabus overlap vs verified individual mastery across exam pairs and test different daily-hour/timeline scenarios.

---

## 5. Study Plans (Preview, Confirmation & Task Tracking)

- **Via AI Counsellor:** Ask `"Create a preparation plan for UPSC CSE based on my current assessment evidence, my available study hours and my competency gaps. I want to review the proposed plan before activating it."`
  - GovPath AI generates an unpersisted **Proposed Preview Plan (Not Saved or Active)**.
  - Nothing is saved until you click **Confirm & Apply** on the proposal card below the message.
- **Via Adaptive Study Plan (`/study-plan`):**
  - Adjust **Daily Study Hours** and **Days / Week** and click **Generate / Adapt Weekly Plan**. If an active plan already exists, a **Confirm Plan Replacement** prompt lets you preview before replacing.
  - Mark tasks **Complete** or **Skip**, add custom tasks (**+ Add Task**), or delete tasks. Completing tasks updates your Study Consistency and completed hours metrics without fabricating assessment scores.
- **Reviewing Without Modifying:** In AI Counsellor, queries such as `"Review my current study plan and identify the improvements you would recommend. Do not change the existing plan."` inspect your existing tasks read-only without changing your stored schedule.
