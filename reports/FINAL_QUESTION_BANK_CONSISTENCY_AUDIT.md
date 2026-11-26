# GovPath AI — Final Question Bank Consistency Audit & Release Freeze Report

**Audit Scope:** Curated Question Bank (`backend/app/data/questions_seed.py`), Exam & Competency Schema (`backend/app/data/exams_seed.py`), Database Records (`backend/govpath_ai.db` & isolated startup seed verification), Selection Logic (`backend/app/routers/assessments.py`), Frontend Assessment Selector (`frontend/src/pages/AssessmentsPage.tsx`), Practice Bank (`frontend/src/pages/PracticePage.tsx`), and Regression/E2E Verification.  
**Release Status:** **PROJECT READY WITH LIMITATIONS — QUESTION BANK VERIFIED**

---

## 1. Executive Summary

A full individual audit of all **54 seeded questions** across **18 competencies** and **10 subjects** confirmed that every question in `backend/app/data/questions_seed.py` is factually accurate, free of duplicates or near-duplicates, equipped with valid 4-option arrays (`0 <= correct_index < 4`) and explanations, and topically aligned to its assigned `competency_id`, `subject_id`, and `topic_name`.

However, live API testing uncovered the **exact root cause** of mixed-topic questions previously observed during assessments, along with two related selection and UI alignment issues:

1. **Root Cause of Mixed-Topic Leakage (`assessments.py`):** Whenever a user started a filtered assessment (`competency_id` or `subject_id`) whose pool contained fewer items than `question_count` (for example, any single competency = `3` questions or single-competency subjects `SCIENCE_TECH`, `CURRENT_AFFAIRS`, `REASONING`, `ENGLISH`, `STATE_TN` = `3` questions each, while the UI dropdown started at `5` questions), `start_assessment` padded the remaining slots with random questions from across the entire database (`all_qs`), injecting unrelated subjects/competencies into focused topic quizzes and revision checks.
2. **Exam-Wide Mock Imbalance & Out-of-Syllabus Leakage (`assessments.py`):** Unfiltered exam mocks (`UPSC_CSE`, `TNPSC_GRP1`, `SSC_CGL`, etc.) sliced `pool[:question_count]` in database insertion order—causing a 12-question `UPSC_CSE` mock to return only `POLITY` and `ECONOMY` questions—and did not cross-check `ExamCompetencyRequirement`, allowing questions mapped to an exam in `exam_mappings` outside that exam's syllabus requirements to appear ahead of core required competencies.
3. **UI Filter Alignment (`AssessmentsPage.tsx`):** The frontend `/assessments` page exposed `Subject Focus` starting at `5 Questions`, with no `3 Questions` option and no `Topic Focus` (`competency_id`) selector even though `/api/assessments` already returned `competencies`.
4. **On-Disk DB Sync Observation (`backend/govpath_ai.db`):** Read-only inspection showed the static on-disk `backend/govpath_ai.db` held `32` rows created prior to Phase 1.8 expansion. App startup (`lifespan` -> `seed_database(db)` in `backend/app/seed.py`) idempotently inserts missing IDs (`if q["id"] not in existing_qs: db.add(Question(**q))`), bringing fresh or restarted backend databases to all **54** questions.

Minimal surgical repairs were implemented in `backend/app/routers/assessments.py` and `frontend/src/pages/AssessmentsPage.tsx`, backed by regression unit/API tests (`backend/tests/test_phase18_release_hardening.py`) and isolated headless Chromium Playwright verification.

---

## 2. Complete Inventory of All 54 Questions (Grouped by Competency)

Verification checks across all 54 items in `backend/app/data/questions_seed.py`:
- **Unique IDs:** 54 / 54 unique (`LEN_IDS: 54`)
- **Structure Validity:** 54 / 54 have 4 options, valid `correct_index`, and non-empty explanation (`VALID_OPTS: True`)
- **Duplicate / Near-Duplicate Check:** `NEAR_DUPLICATES: []` (pairwise prompt similarity threshold `> 0.65`)
- **Distribution:** `3` questions per competency across all `18` competencies (`18 * 3 = 54`)

| Subject | Competency ID (`Name`) | Question ID | Difficulty | Verified Topic & Answer Key | Exam Mappings | Audit Verdict |
|---|---|---|---|---|---|---|
| `POLITY` | `COMP_POL_CONSTITUTION` (Constitution) | `Q_POL_CON_01` | `easy` | SC writ jurisdiction — `Article 32` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `SSC_CHSL`, `RRB_NTPC`, `UPSC_CDS` | Verified Accurate & Aligned |
| `POLITY` | `COMP_POL_CONSTITUTION` | `Q_POL_CON_02` | `medium` | Preamble 42nd Amendment & Kesavananda Bharati — `Both 1 and 2` (`idx=2`) | `UPSC_CSE`, `TNPSC_GRP1`, `UPSC_CDS` | Verified Accurate & Aligned |
| `POLITY` | `COMP_POL_CONSTITUTION` | `Q_POL_CON_03` | `easy` | Article 21A Right to Education — `6 to 14 years` (`idx=1`) | `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `SSC_CHSL`, `RRB_NTPC` | Verified Accurate & Aligned |
| `POLITY` | `COMP_POL_PARLIAMENT` (Parliament & Executive) | `Q_POL_PAR_01` | `medium` | Money Bill Art. 110 exception — `Joint sitting NOT applicable` (`idx=3`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `UPSC_CDS` | Verified Accurate & Aligned |
| `POLITY` | `COMP_POL_PARLIAMENT` | `Q_POL_PAR_02` | `medium` | Lok Sabha-only committee — `Estimates Committee` (`idx=2`) | `UPSC_CSE`, `TNPSC_GRP1`, `SSC_CGL`, `UPSC_CDS` | Verified Accurate & Aligned |
| `POLITY` | `COMP_POL_PARLIAMENT` | `Q_POL_PAR_03` | `easy` | Parliamentary quorum Art. 100(3) — `One-tenth of total members` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `UPSC_CDS` | Verified Accurate & Aligned |
| `POLITY` | `COMP_POL_JUDICIARY` (Judiciary) | `Q_POL_JUD_01` | `easy` | Writ for entitlement to public office — `Quo Warranto` (`idx=2`) | `UPSC_CSE`, `TNPSC_GRP1`, `SSC_CGL`, `UPSC_CDS` | Verified Accurate & Aligned |
| `POLITY` | `COMP_POL_JUDICIARY` | `Q_POL_JUD_02` | `hard` | Art. 143 SC advisory jurisdiction — `Mandatory on Art. 143(2), advisory` (`idx=2`) | `UPSC_CSE`, `TNPSC_GRP1` | Verified Accurate & Aligned |
| `POLITY` | `COMP_POL_JUDICIARY` | `Q_POL_JUD_03` | `medium` | Art. 131 Exclusive Original Jurisdiction — `Union-State / Inter-State disputes` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `UPSC_CDS` | Verified Accurate & Aligned |
| `POLITY` | `COMP_POL_FEDERALISM` (Federalism & Governance) | `Q_POL_FED_01` | `easy` | Panchayati Raj Part IX / 11th Schedule — `73rd Amendment Act` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `RRB_NTPC` | Verified Accurate & Aligned |
| `POLITY` | `COMP_POL_FEDERALISM` | `Q_POL_FED_02` | `medium` | Finance Commission Art. 280 mandate — `Tax devolution Union-States` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL` | Verified Accurate & Aligned |
| `POLITY` | `COMP_POL_FEDERALISM` | `Q_POL_FED_03` | `medium` | Inter-State Council constitutional basis — `Article 263` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL` | Verified Accurate & Aligned |
| `ECONOMY` | `COMP_ECO_MACRO` (Money & Banking) | `Q_ECO_MAC_01` | `medium` | RBI Repo Rate hike transmission — `Higher bank borrowing cost moderates demand` (`idx=0`) | `UPSC_CSE`, `TNPSC_GRP1`, `IBPS_PO`, `SSC_CGL` | Verified Accurate & Aligned |
| `ECONOMY` | `COMP_ECO_MACRO` | `Q_ECO_MAC_02` | `medium` | Compiler of CPI (Combined) — `National Statistical Office (NSO), MoSPI` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `IBPS_PO` | Verified Accurate & Aligned |
| `ECONOMY` | `COMP_ECO_MACRO` | `Q_ECO_MAC_03` | `medium` | CRR vs SLR distinction — `CRR cash at RBI; SLR held by banks in liquid assets` (`idx=0`) | `UPSC_CSE`, `TNPSC_GRP1`, `IBPS_PO`, `SSC_CGL` | Verified Accurate & Aligned |
| `ECONOMY` | `COMP_ECO_FISCAL` (Public Finance) | `Q_ECO_FIS_01` | `easy` | Primary Deficit formula — `Fiscal Deficit minus Interest Payments` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `IBPS_PO`, `SSC_CGL` | Verified Accurate & Aligned |
| `ECONOMY` | `COMP_ECO_FISCAL` | `Q_ECO_FIS_02` | `medium` | Capital Receipt example — `Disinvestment proceeds from PSU equity sale` (`idx=2`) | `UPSC_CSE`, `TNPSC_GRP1`, `IBPS_PO` | Verified Accurate & Aligned |
| `ECONOMY` | `COMP_ECO_FISCAL` | `Q_ECO_FIS_03` | `easy` | GST Council constitutional article — `Article 279A` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `IBPS_PO`, `SSC_CGL` | Verified Accurate & Aligned |
| `ECONOMY` | `COMP_ECO_GROWTH` (Development & Trade) | `Q_ECO_GRW_01` | `medium` | BoP remittances entry — `Current Account — Secondary Income` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `IBPS_PO` | Verified Accurate & Aligned |
| `ECONOMY` | `COMP_ECO_GROWTH` | `Q_ECO_GRW_02` | `easy` | Gini Coefficient near 1 — `High degree of income inequality` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `IBPS_PO`, `SSC_CGL` | Verified Accurate & Aligned |
| `ECONOMY` | `COMP_ECO_GROWTH` | `Q_ECO_GRW_03` | `medium` | Body recommending MSP — `CACP` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `IBPS_PO` | Verified Accurate & Aligned |
| `HISTORY` | `COMP_HIS_MODERN` (Modern History) | `Q_HIS_MOD_01` | `easy` | Chronology: Champaran, Rowlatt, NCM, Gandhi-Irwin — `1 - 3 - 2 - 4` (`idx=0`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `RRB_NTPC`, `UPSC_CDS` | Verified Accurate & Aligned |
| `HISTORY` | `COMP_HIS_MODERN` | `Q_HIS_MOD_02` | `easy` | Self-Respect Movement founder (1925) — `E.V. Ramasamy (Periyar)` (`idx=1`) | `TNPSC_GRP1`, `TNPSC_GRP2`, `UPSC_CSE` | Verified Accurate & Aligned |
| `HISTORY` | `COMP_HIS_MODERN` | `Q_HIS_MOD_03` | `medium` | Dyarchy in provinces Act — `Government of India Act, 1919` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `UPSC_CDS` | Verified Accurate & Aligned |
| `HISTORY` | `COMP_HIS_ANCIENT_CULTURE` (Ancient & Culture) | `Q_HIS_CUL_01` | `easy` | Stepped Vimana & Gopurams style — `Dravida Style` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `SSC_CGL`, `UPSC_CDS` | Verified Accurate & Aligned |
| `HISTORY` | `COMP_HIS_ANCIENT_CULTURE` | `Q_HIS_CUL_02` | `medium` | Kalinga War & Dhamma-Vijaya edict — `Major Rock Edict XIII` (`idx=2`) | `UPSC_CSE`, `TNPSC_GRP1`, `SSC_CGL`, `UPSC_CDS` | Verified Accurate & Aligned |
| `HISTORY` | `COMP_HIS_ANCIENT_CULTURE` | `Q_HIS_CUL_03` | `easy` | Nirguna Bhakti exponent — `Kabir` (`idx=2`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `RRB_NTPC` | Verified Accurate & Aligned |
| `GEOGRAPHY` | `COMP_GEO_INDIAN_PHYSICAL` (Physical & Indian Geography) | `Q_GEO_PHY_01` | `medium` | Coromandel Oct–Dec rainfall — `Western Ghats shadow + NE Monsoon` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `UPSC_CDS` | Verified Accurate & Aligned |
| `GEOGRAPHY` | `COMP_GEO_INDIAN_PHYSICAL` | `Q_GEO_PHY_02` | `medium` | Narmada & Tapi estuaries — `Rift valleys over hard rocky terrain` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `SSC_CGL`, `UPSC_CDS`, `RRB_NTPC` | Verified Accurate & Aligned |
| `GEOGRAPHY` | `COMP_GEO_INDIAN_PHYSICAL` | `Q_GEO_PHY_03` | `easy` | Regur / Deccan basalt soil — `Black Cotton Soil` (`idx=2`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `RRB_NTPC` | Verified Accurate & Aligned |
| `GEOGRAPHY` | `COMP_GEO_ENV` (Environment & Ecology) | `Q_GEO_ENV_01` | `easy` | Ramsar Convention focus — `Wetlands` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `SSC_CGL`, `UPSC_CDS` | Verified Accurate & Aligned |
| `GEOGRAPHY` | `COMP_GEO_ENV` | `Q_GEO_ENV_02` | `easy` | 1987 Ozone-depleting substances treaty — `Montreal Protocol` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `SSC_CGL`, `RRB_NTPC`, `UPSC_CDS` | Verified Accurate & Aligned |
| `GEOGRAPHY` | `COMP_GEO_ENV` | `Q_GEO_ENV_03` | `medium` | NTCA statutory Act — `Wildlife (Protection) Act, 1972 (as amended in 2006)` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `UPSC_CDS` | Verified Accurate & Aligned |
| `SCIENCE_TECH` | `COMP_SCI_GENERAL` (Core Science & Tech) | `Q_SCI_01` | `medium` | mRNA vs inactivated vaccines — `Genetic instructions for antigen protein` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `RRB_NTPC`, `UPSC_CDS` | Verified Accurate & Aligned |
| `SCIENCE_TECH` | `COMP_SCI_GENERAL` | `Q_SCI_02` | `easy` | Optical fibre principle — `Total Internal Reflection (TIR)` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `RRB_NTPC`, `UPSC_CDS` | Verified Accurate & Aligned |
| `SCIENCE_TECH` | `COMP_SCI_GENERAL` | `Q_SCI_03` | `medium` | Cryogenic engine propellants (LVM3 C25) — `Liquid Hydrogen + Liquid Oxygen` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `SSC_CGL`, `RRB_NTPC`, `UPSC_CDS` | Verified Accurate & Aligned |
| `CURRENT_AFFAIRS` | `COMP_CA_POLICY` (Current Affairs & Schemes) | `Q_CA_01` | `medium` | Foundational India Stack DPI — `Aadhaar, UPI, DigiLocker / DEPA` (`idx=0`) | `UPSC_CSE`, `TNPSC_GRP1`, `IBPS_PO`, `SSC_CGL`, `UPSC_CDS` | Verified Accurate & Aligned |
| `CURRENT_AFFAIRS` | `COMP_CA_POLICY` | `Q_CA_02` | `easy` | Economic Survey publisher — `Department of Economic Affairs, MoF` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `IBPS_PO`, `SSC_CGL`, `RRB_NTPC` | Verified Accurate & Aligned |
| `CURRENT_AFFAIRS` | `COMP_CA_POLICY` | `Q_CA_03` | `easy` | NITI Aayog status — `2015 executive resolution think tank` (`idx=1`) | `UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `IBPS_PO`, `SSC_CGL`, `RRB_NTPC` | Verified Accurate & Aligned |
| `QUANT` | `COMP_QNT_ARITHMETIC` (Arithmetic & Number Systems) | `Q_QNT_ARI_01` | `medium` | Successive spending budget (`65%`, `20%` rem, saves 1400) — `Rs. 5,000` (`idx=1`) | `SSC_CGL`, `SSC_CHSL`, `IBPS_PO`, `RRB_NTPC`, `TNPSC_GRP1`, `TNPSC_GRP2`, `UPSC_CSE`, `UPSC_CDS` | Verified Accurate & Aligned |
| `QUANT` | `COMP_QNT_ARITHMETIC` | `Q_QNT_ARI_02` | `medium` | Pipes A (12h) & B (18h), 4h together -> rem B — `8 hours` (`idx=1`) | `SSC_CGL`, `SSC_CHSL`, `IBPS_PO`, `RRB_NTPC`, `TNPSC_GRP2`, `UPSC_CDS` | Verified Accurate & Aligned |
| `QUANT` | `COMP_QNT_ARITHMETIC` | `Q_QNT_ARI_03` | `easy` | CI - SI on Rs. 10,000 at 10% for 2 yrs — `Rs. 100` (`idx=1`) | `SSC_CGL`, `SSC_CHSL`, `IBPS_PO`, `RRB_NTPC`, `TNPSC_GRP1`, `TNPSC_GRP2`, `UPSC_CDS` | Verified Accurate & Aligned |
| `QUANT` | `COMP_QNT_ADV_DI` (DI & Advanced Math) | `Q_QNT_DI_01` | `easy` | Weighted average (40*72 + 60*82)/100 — `78` (`idx=2`) | `SSC_CGL`, `IBPS_PO`, `RRB_NTPC`, `UPSC_CSE`, `UPSC_CDS` | Verified Accurate & Aligned |
| `QUANT` | `COMP_QNT_ADV_DI` | `Q_QNT_DI_02` | `easy` | Algebra `x + 1/x = 5` => `x^2 + 1/x^2` — `23` (`idx=1`) | `SSC_CGL`, `SSC_CHSL`, `UPSC_CDS`, `RRB_NTPC` | Verified Accurate & Aligned |
| `QUANT` | `COMP_QNT_ADV_DI` | `Q_QNT_DI_03` | `easy` | Cylinder `r -> 2r, h -> h/2` — `Becomes 2 times` (`idx=1`) | `SSC_CGL`, `SSC_CHSL`, `RRB_NTPC`, `UPSC_CDS`, `TNPSC_GRP1` | Verified Accurate & Aligned |
| `REASONING` | `COMP_RSN_ANALYTICAL` (Analytical & Verbal Reasoning) | `Q_RSN_01` | `medium` | Syllogism: All Policies->Frameworks, Some Frameworks->Regs — `Only II follows` (`idx=1`) | `IBPS_PO`, `SSC_CGL`, `SSC_CHSL`, `RRB_NTPC`, `UPSC_CSE` | Verified Accurate & Aligned |
| `REASONING` | `COMP_RSN_ANALYTICAL` | `Q_RSN_02` | `easy` | Number series `7, 15, 31, 63, 127, ?` — `255` (`idx=2`) | `SSC_CGL`, `SSC_CHSL`, `IBPS_PO`, `RRB_NTPC`, `TNPSC_GRP1`, `TNPSC_GRP2` | Verified Accurate & Aligned |
| `REASONING` | `COMP_RSN_ANALYTICAL` | `Q_RSN_03` | `easy` | Caesar `+1` shift `POLITY -> QPMJUZ`, `EXAM -> ?` — `FYBN` (`idx=0`) | `SSC_CGL`, `SSC_CHSL`, `IBPS_PO`, `RRB_NTPC`, `TNPSC_GRP2`, `UPSC_CSE` | Verified Accurate & Aligned |
| `ENGLISH` | `COMP_ENG_COMPREHENSION` (Comprehension & Grammar) | `Q_ENG_01` | `easy` | `Neither ... nor` verb agreement — `were willing to sign` (`idx=1`) | `SSC_CGL`, `SSC_CHSL`, `IBPS_PO`, `UPSC_CDS` | Verified Accurate & Aligned |
| `ENGLISH` | `COMP_ENG_COMPREHENSION` | `Q_ENG_02` | `easy` | Antonym of `EPHEMERAL` — `Enduring` (`idx=1`) | `SSC_CGL`, `SSC_CHSL`, `IBPS_PO`, `UPSC_CDS` | Verified Accurate & Aligned |
| `ENGLISH` | `COMP_ENG_COMPREHENSION` | `Q_ENG_03` | `easy` | Prepositional collocation `comply ____` — `with` (`idx=1`) | `SSC_CGL`, `SSC_CHSL`, `IBPS_PO`, `UPSC_CDS` | Verified Accurate & Aligned |
| `STATE_TN` | `COMP_TN_HERITAGE_ADMIN` (TN History & Administration) | `Q_TN_01` | `medium` | Ainkurunuru (Akam) & Purananuru (Puram) classification (`idx=1`) | `TNPSC_GRP1`, `TNPSC_GRP2` | Verified Accurate & Aligned |
| `STATE_TN` | `COMP_TN_HERITAGE_ADMIN` | `Q_TN_02` | `medium` | Justice Party 1925/1927 temple act — `Hindu Religious Endowments (HRE) Act` (`idx=1`) | `TNPSC_GRP1`, `TNPSC_GRP2` | Verified Accurate & Aligned |
| `STATE_TN` | `COMP_TN_HERITAGE_ADMIN` | `Q_TN_03` | `easy` | Thirukkural structure — `1,330 couplets across 133 chapters` (`idx=1`) | `TNPSC_GRP1`, `TNPSC_GRP2` | Verified Accurate & Aligned |

---

## 3. Root Causes Diagnosed & Minimal Surgical Repairs Applied

### 3.1 Backend Selection Logic (`backend/app/routers/assessments.py`)
1. **Before Repair:**
   - Filtered assessments (`competency_id` or `subject_id`) executed `extras = [q for q in all_qs if q not in selected]` whenever `len(selected) < min(payload.question_count, len(all_qs))`. Because each competency holds `3` items and 5 subjects (`SCIENCE_TECH`, `CURRENT_AFFAIRS`, `REASONING`, `ENGLISH`, `STATE_TN`) hold `3` items total, requesting `5` questions (previously the UI minimum) always returned `3` on-topic + `2` random off-topic questions.
   - Passing an unrecognized `competency_id` or `subject_id` silently ignored the filter and fell back to Polity questions.
   - Unfiltered exam mocks returned questions in raw SQLite insertion order (e.g., `UPSC_CSE count=12` returned only `POLITY` and `ECONOMY`) and did not prioritize `ExamCompetencyRequirement` items over extra `exam_mappings` entries.
2. **Repairs Implemented:**
   - **Strict Competency & Subject Isolation:** `start_assessment` never pads across unrelated competencies or subjects when `competency_id` or `subject_id` is supplied. When fewer items exist than requested (`< payload.question_count`), it returns all matching items cleanly and includes an explanatory `selection_note` in the API response.
   - **Explicit Filter Validation:** Unknown `competency_id` or `subject_id` rejects with HTTP `400` instead of silent fallback.
   - **Syllabus-Prioritized Multi-Competency Interleaving (Exam-Wide Mocks/Diagnostics):** Added `_interleave_by_competency` so unfiltered exam assessments (`diagnostic`, `mock_test`, `revision`) prioritize questions matching both `exam_mappings` and `ExamCompetencyRequirement`, distributing across distinct competencies round-robin before repeating any competency.
   - **Backward Compatibility Preserved:** Subject-filtered ordering retains existing within-subject progression (preserving weak/revision prioritization when `assessment_type == "revision"` and preserving all Phase 1.6 / Phase 1.7 tests unmodified).

### 3.2 Frontend UI Alignment (`frontend/src/pages/AssessmentsPage.tsx`)
- Added `Topic Focus (Optional)` (`competencyId`) dropdown populated from `/api/assessments` (`res.competencies`), automatically kept consistent with `Subject Focus` (`subjectId`).
- Added `<option value={3}>3 Questions (~4 mins)</option>` alongside `5, 8, 12, 15, 25` so users can launch focused 3-question competency/subject checks matching bank granularity.
- Displayed `activeTest.selection_note` when fewer filtered questions exist than requested.

---

## 4. Verification Matrix & Results (Post-Final-Edit)

| Check | Scope & Conditions | Outcome |
|---|---|---|
| Full Backend Suite (`pytest backend\tests -v`) | Isolated temporary SQLite DBs; includes Phase 1, 1.6, 1.7, 1.8 & new `test_p18_question_bank_selection_purity_and_balance` | **42 passed in 36.22s** |
| Frontend Build (`npm --prefix frontend run build`) | TypeScript compilation (`tsc`) + Vite production bundle | **Exited 0** (`dist/assets/index-DcFK2dX0.js`, 16.25s) |
| Competency API Matrix (`scratch/test_api_selection.py`) | All 18 competencies at `count=3` and `COMP_POL_CONSTITUTION`, `COMP_SCI_GENERAL`, `COMP_TN_HERITAGE_ADMIN` at `count=5` | **18/18 returned strictly pure competency questions (0 off-topic leakage)** |
| Subject & Revision API Matrix (`scratch/test_api_selection.py`) | All 10 subjects (`count=5`) + `revision` mode on `SCIENCE_TECH` (`count=5`) | **10/10 returned strictly pure subject questions (3/3 for 3-Q subjects, 5/5 for multi-comp subjects)** |
| Exam-Wide Mocks (`count=12`) | All 8 exams (`UPSC_CSE`, `TNPSC_GRP1`, `TNPSC_GRP2`, `SSC_CGL`, `SSC_CHSL`, `IBPS_PO`, `RRB_NTPC`, `UPSC_CDS`) | **UPSC_CSE & TNPSC_GRP1 spanned 12 distinct competencies (`0` warnings across all 8 exams)** |
| Practice Filtering (`GET /api/practice/questions`) | `subject_id=POLITY/SCIENCE_TECH/STATE_TN` & `competency_id=COMP_POL_JUDICIARY` | **100% exact filter matches (`12`, `3`, `3`, `3`)** |
| Headless Chromium Playwright E2E | Isolated backend + Vite preview; Demo login -> `/assessments` (`SCIENCE_TECH` 5 requested -> 3/3 Pure + notice -> submit; `COMP_POL_JUDICIARY` 3/3 Pure -> submit) -> `/practice` (`STATE_TN` 3 Qs) | **PASSED — 0 console errors, 0 page errors, 0 server 5xx** |

---

## 5. Adequacy Evaluation & Explicit Limitations

### Is 3 Questions per Competency (54 Total) Sufficient?
- **Sufficient for Controlled Demonstration & Agentic Verification:** At `3` curated questions per competency (`54` total), every one of the 18 competencies supports standalone multi-question accuracy differentiation (`0%`, `33.3%`, `66.7%`, `100%`), spaced retention updates, error-pattern diagnosis, and pure competency/subject topic quizzes without mixed-topic leakage.
- **Not Sufficient for Full-Length High-Stakes Practice Production:** Larger production banks (e.g., 25–100+ items per competency) would be needed before live commercial rollout so repeat quizzes and 25–100 question full-length mocks draw fresh unseen items.

### Explicit Remaining Limitations (Non-Blocking for Release Freeze)
1. **Static `backend/govpath_ai.db` on Disk Prior to App Startup:** Currently stores `32` historical rows on disk until the backend starts (`main.py` lifespan calls `seed_database`, which inserts the remaining `22` Phase 1.8 items to `54`).
2. **Mapped Question Coverage for `SSC_CHSL` and Selected Exam Mappings:** Four competencies required by `SSC_CHSL` (`COMP_HIS_MODERN`, `COMP_GEO_INDIAN_PHYSICAL`, `COMP_SCI_GENERAL`, `COMP_CA_POLICY`), one by `UPSC_CSE` (`COMP_ENG_COMPREHENSION`), and one by `TNPSC_GRP2` (`COMP_ECO_MACRO`) omit that specific exam tag in `exam_mappings`. For competency/subject quizzes, the repaired fallback completes cleanly from the same competency/subject in `all_qs`; for short (`12`-question) `SSC_CHSL` mocks, `tier_primary` covers its `5` explicitly mapped competencies (`15` items) before touching secondary unmapped items.
3. **25-Question Mock Repetition on Small Exams:** Exams with 7–9 required competencies (21–27 mapped items) exhaust strictly-required items near count 25 and append fallback items up to the requested mock length.

---

## 6. Release Freeze Decision

All Phase 1–1.8 agentic workflows, question bank inventory integrity, strict topic/subject isolation, balanced mock distribution, frontend filter controls, and end-to-end tests are verified green. Temporary `backend/test_govpath.db` was cleaned up.

**Final Release Status:** `PROJECT READY WITH LIMITATIONS — QUESTION BANK VERIFIED`
