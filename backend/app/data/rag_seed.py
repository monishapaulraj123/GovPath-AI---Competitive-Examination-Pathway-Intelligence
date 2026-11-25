"""Curated and verified reference documents for GovPath AI RAG Knowledge Base."""

RAG_DOCUMENTS_SEED = [
    {
        "title": "UPSC Civil Services Examination (CSE) — Syllabus & Structure Overview",
        "exam_id": "UPSC_CSE",
        "doc_type": "Official Syllabus Reference",
        "source_name": "Union Public Service Commission (upsc.gov.in)",
        "source_url": "https://upsc.gov.in",
        "verified_status": "Verified Structural Reference (Check portal for annual dates/vacancies)",
        "content": (
            "The UPSC Civil Services Examination (CSE) consists of three sequential stages: "
            "1) Preliminary Examination (Objective type) comprising General Studies Paper I (200 marks, merit for Prelims cutoff) and General Studies Paper II / CSAT (200 marks, qualifying at 33%). "
            "2) Main Examination (Written descriptive, 1750 marks across Essay, GS Paper I, GS Paper II, GS Paper III, GS Paper IV Ethics, and two Optional Subject papers, plus two qualifying language papers). "
            "3) Personality Test / Interview (275 marks). "
            "Core General Studies competencies include Indian Heritage and Culture, Modern History, Physical & Indian Geography, Indian Constitution, Polity, Governance & International Relations, "
            "Indian Economy, Agriculture, Environment & Ecology, Science & Technology, Internal Security, and Ethics, Integrity & Aptitude. "
            "Note: Official notification dates, age cutoffs, attempt limits, and vacancy counts must always be verified directly on upsc.gov.in for the active cycle."
        ),
    },
    {
        "title": "TNPSC Group I & Group II/IIA — Examination Structure & Unit 8/9 Competency Guide",
        "exam_id": "TNPSC_GRP1",
        "doc_type": "Official Syllabus Reference",
        "source_name": "Tamil Nadu Public Service Commission (tnpsc.gov.in)",
        "source_url": "https://www.tnpsc.gov.in",
        "verified_status": "Verified Structural Reference (Check portal for active cycle rules)",
        "content": (
            "TNPSC Combined Civil Services Examination-I (Group I) selects candidates for premier state administrative posts such as Deputy Collector, Deputy Superintendent of Police, and Assistant Commissioner. "
            "The Preliminary syllabus covers General Science, Current Events, Geography, History and Culture of India, Indian Polity, Indian Economy, Indian National Movement, "
            "Unit VIII (History, Culture, Heritage and Socio-Political Movements in Tamil Nadu including Thirukkural), Unit IX (Development Administration in Tamil Nadu), and Aptitude & Mental Ability. "
            "Aspirants preparing for UPSC CSE already cover substantial overlap in Indian Polity, Economy, Modern History, Geography, and Science, while needing targeted state-specific reinforcement in Unit VIII and Unit IX plus Tamil Eligibility Paper readiness. "
            "Always verify current cycle Tamil eligibility rules, dates, and vacancies on tnpsc.gov.in."
        ),
    },
    {
        "title": "SSC CGL & CHSL — Scheme of Examination & Quantitative/Reasoning Competencies",
        "exam_id": "SSC_CGL",
        "doc_type": "Official Syllabus Reference",
        "source_name": "Staff Selection Commission (ssc.gov.in)",
        "source_url": "https://ssc.gov.in",
        "verified_status": "Verified Structural Reference (Check portal for active cycle rules)",
        "content": (
            "SSC Combined Graduate Level (CGL) conducts Tier-I (qualifying/screening CBT of 60 minutes covering General Intelligence & Reasoning, General Awareness, Quantitative Aptitude, and English Comprehension) "
            "and Tier-II (merit-determining Computer-Based Examination combining Mathematical Abilities, Reasoning & General Intelligence, English Language & Comprehension, General Awareness, Computer Knowledge, and Data Entry Speed Test). "
            "Unlike UPSC CSE, SSC CGL demands high speed and accuracy in Quantitative Arithmetic, Algebra, Geometry, Trigonometry, Mensuration, Analytical Reasoning, and English Grammar/Comprehension, alongside concise factual General Awareness. "
            "SSC CHSL shares a highly overlapping skill profile at the 10+2 level, enabling strong bidirectional transfer between SSC CGL and SSC CHSL."
        ),
    },
    {
        "title": "IBPS PO Banking Examination — Sectional Pattern & Financial Awareness",
        "exam_id": "IBPS_PO",
        "doc_type": "Official Syllabus Reference",
        "source_name": "Institute of Banking Personnel Selection (ibps.in)",
        "source_url": "https://www.ibps.in",
        "verified_status": "Verified Structural Reference (Check portal for active cycle rules)",
        "content": (
            "IBPS Probationary Officer (CRP PO/MT) includes Prelims (100 objective questions across English Language, Quantitative Aptitude, and Reasoning Ability with strict 20-minute sectional timers), "
            "Mains (Reasoning & Computer Aptitude, General/Economy/Banking Awareness, English Language, Data Analysis & Interpretation, plus Descriptive English Letter & Essay), and Interview. "
            "Success depends heavily on timed Data Interpretation, seating/scheduling puzzles, reading comprehension, and RBI monetary policy / banking awareness. "
            "There is moderate transfer from SSC CGL in Quant, Reasoning, and English, and from UPSC Economy in Monetary & Fiscal policy."
        ),
    },
    {
        "title": "RRB NTPC & UPSC CDS — Eligibility Boundaries & Core Preparation Overlap",
        "exam_id": "RRB_NTPC",
        "doc_type": "Official Syllabus Reference",
        "source_name": "RRB / UPSC Official Portals",
        "source_url": "https://www.rrbcdg.gov.in",
        "verified_status": "Verified Structural Reference (Check portals for active cycle rules)",
        "content": (
            "RRB NTPC evaluates Mathematics, General Intelligence & Reasoning, and General Awareness (Science, History, Polity, Geography, Current Affairs) across CBT-1 and CBT-2, followed by CBAT/Typing where applicable. "
            "UPSC CDS recruits officers for IMA, INA, AFA, and OTA through objective papers in English, General Knowledge, and Elementary Mathematics (except OTA), followed by a 5-day SSB Interview. "
            "UPSC CSE and SSC CGL aspirants possess significant transferable General Knowledge and Aptitude foundations for both RRB NTPC and UPSC CDS, subject to strict age, educational stream, and medical eligibility checks."
        ),
    },
    {
        "title": "GovPath AI Readiness, Gap Analysis & Knowledge Transfer Methodology",
        "exam_id": None,
        "doc_type": "System Methodology Documentation",
        "source_name": "GovPath AI Academic Intelligence Engine",
        "source_url": "",
        "verified_status": "Internal Verified Methodology",
        "content": (
            "GovPath AI computes Student Readiness as a weighted competency alignment index (0-100), NOT as an official probability of clearing an examination. "
            "Competency evidence aggregates diagnostic tests (weight 1.15), mock tests (weight 1.35), topic/subject quizzes (weight 1.0), and revision checks (weight 0.85) with exponential recency weighting (half-life ~21 days) and evidence-count confidence scaling. "
            "Gap Analysis compares target examination required competency depth against demonstrated student evidence. "
            "Knowledge Transfer classifies each target exam competency as Fully Transferable (covered in source exam at >= target depth and student evidence >= 65% of target), Partially Transferable (shared competency with depth mismatch or moderate evidence), Requires Reinforcement (low demonstrated evidence despite syllabus overlap), or Not Covered (absent from source exam). "
            "Estimated effort hours are transparent model approximations assuming ~0.35 hours per depth-gap point adjusted by base competency hours."
        ),
    },
]
