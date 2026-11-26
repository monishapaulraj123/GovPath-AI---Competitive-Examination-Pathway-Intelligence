# GovPath AI — Testing & Validation Documentation

## 1. Test Setup & Databases

All automated tests run against **isolated ephemeral SQLite databases** set via `DATABASE_URL` inside each test module so the development/demo database (`backend/govpath_ai.db`) is never modified:
- `test_api.py` → `test_govpath.db`
- `test_orchestrator_phase1.py` → `test_phase1_govpath.db`
- `test_phase16_acceptance.py` → `test_phase16_govpath.db`
- `test_phase17_student_journey.py` → `test_phase17_govpath.db`
- `test_phase18_release_hardening.py` → `test_phase18_govpath.db`

*(Remove temporary `backend/test_*.db` files after manual cleanup if interrupted mid-run.)*

---

## 2. Running the Suites

### Backend Full Suite
```bash
cd backend
pytest -v
```
Current suite size: **41 tests** across 5 modules.

### Frontend TypeScript & Bundle Verification
```bash
cd frontend
npm run build
```

---

## 3. Test Suites & Coverage

| Suite | File | Scope |
|---|---|---|
| Core API Workflow | `backend/tests/test_api.py` | Spins up local Uvicorn server and verifies auth, dashboard, engines, assessment lifecycle, study plan mutations, and counsellor chat |
| Phase 1 & 1.5 Orchestrator | `backend/tests/test_orchestrator_phase1.py` | Structured intent classification, dynamic agent/tool selection, mocked LLM structured planning (`requests.post`), numeric grounding guardrail, `429`/`500`/`503`/timeout/malformed JSON fallbacks, missing OpenAI path verification, prompt injection sanitization, cross-user checks, empty-DB/no-profile recovery, bounded question-count recommendation invariants |
| Phase 1.6 Acceptance | `backend/tests/test_phase16_acceptance.py` | Cross-workflow adaptation (`Test A` transfer, `Test B` feasibility, `Test C` preview + `/apply-proposal` idempotency, `Test D` chronological progress + adaptive diagnosis), adversarial constraints (`E1`–`E6` multi-verb/conflicting/ambiguous/no-modify/no-activate), LLM failures (`F1`–`F10`), trace authenticity (`G`) |
| Phase 1.7 Student Journey | `backend/tests/test_phase17_student_journey.py` | Preparation investigation profiles, live REST `/assessments/start` → `submit` (with unanswered/incorrect items + duplicate submit idempotency + cross-user `404`), immediate post-assessment evidence update, sequential E1 improvement vs E2 decline adaptation, study plan lifecycle, 10-query cross-workflow consistency |
| Phase 1.8 Release Hardening | `backend/tests/test_phase18_release_hardening.py` | All 18 competencies `>= 3` curated questions with uniqueness & valid exam/competency mappings, idempotent `seed_database`, SQLite `PRAGMA foreign_keys=ON`, inactive-user `401`, generic JWT error (no exception leak), strict CORS origin check, SQLi payload safety, 17-step E2E smoke test |

---

## 4. Browser E2E Verification (Isolated Playwright Chromium)

Automated browser verification uses Python `playwright` (`sync_playwright().chromium.launch(headless=True)`) inside an isolated browser context (`browser.new_context(...)`) connected to ephemeral local servers (`uvicorn` on `:8000` backed by a disposable SQLite DB with `LLM_PROVIDER=none`, and Vite on `:5173`), covering:
- Negative login validation error (`Invalid email or password`)
- Registration with non-default target exam (`SSC_CGL`) → Dashboard (`0%` readiness)
- Assessments page default target verification (`SSC_CGL`) → 5-question test completion → breakdown & explanations
- Updated Dashboard (`1 assessments logged`), Retention Tracker, and Performance Analytics pages
- Study Plan creation, task completion toggle, and active plan replacement confirmation guard
- AI Counsellor restricted investigation trace UI (`Deterministic Fallback`, `No Plan / Investigation Only`, expandable details) + preview & `Confirm & Apply` plan activation
- Mobile viewport (`390×844`) navigation drawer & Sign Out flow with 0 console errors, 0 page errors, and 0 server 5xx responses

---

## 5. Known Testing Limitations

- **LLM Fallback Dominance in CI:** Automated tests default to `LLM_PROVIDER=none` or mocked `requests.post` responses to avoid exhausting external Gemini free-tier quotas; live Gemini behavior is verified through bounded single-query probes (`gemini-3.1-flash-lite`).
- **Vite Dev Server Proxy in Local Browser Test:** Browser E2E checks validate Vite dev proxy (`/api` → FastAPI); production Nginx/reverse-proxy deployments should verify `/api` routing headers explicitly in the target hosting environment.
