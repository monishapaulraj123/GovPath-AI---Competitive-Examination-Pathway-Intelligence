"""
LLM-Assisted Structured Intent & Workflow Planner + Bounded Evidence Evaluator
with prohibition-aware action constraints and reliable deterministic fallback planning.
"""

from datetime import datetime, timezone
import json
import re
from typing import Any, Optional
import uuid
from sqlalchemy.orm import Session

from app.agents.llm_client import generate_structured_json, get_llm_status
from app.agents.schemas import (
    AgentName,
    FollowUpDecision,
    IntentCategory,
    OrchestrationState,
    PreparationConstraints,
    StructuredPlan,
    ToolExecutionRecord,
    WorkflowActionConstraints,
)
from app.agents.tool_registry import ToolRegistry, sanitize_user_query
from app.config import get_settings
from app.models import Exam, StudentProfile, Subject

EXAM_ALIASES: dict[str, list[str]] = {
    "TNPSC_GRP2": ["tnpsc group 2", "tnpsc group ii", "group 2", "group ii", "group 2a", "tnpsc_grp2"],
    "TNPSC_GRP1": ["tnpsc group 1", "tnpsc group i", "group 1", "group i", "tnpsc", "tnpsc_grp1"],
    "SSC_CHSL": ["ssc chsl", "chsl", "ssc_chsl"],
    "SSC_CGL": ["ssc cgl", "cgl", "ssc", "ssc_cgl"],
    "UPSC_CDS": ["upsc cds", "cds", "defence", "defense", "upsc_cds"],
    "UPSC_CSE": ["upsc cse", "upsc", "cse", "ias", "ips", "civil services", "upsc_cse"],
    "IBPS_PO": ["ibps po", "ibps", "banking", "bank po", "ibps_po"],
    "RRB_NTPC": ["rrb ntpc", "rrb", "railway", "ntpc", "rrb_ntpc"],
}

UNSUPPORTED_EXAM_HINTS = [
    "neet", "jee", "gate", "cat", "clat", "cuet", "gre", "gmat", "sat", "ugc net", "ctet",
]

VALID_AGENTS: tuple[AgentName, ...] = (
    "StudentAnalysisAgent",
    "ExamIntelligenceAgent",
    "PerformanceDiagnosisAgent",
    "KnowledgeTransferAgent",
    "PathwayPlanningAgent",
    "StudyOptimizationAgent",
)

PLAN_NOUNS = r"(?:study\s+plan|weekly\s+plan|timetable|time\s+table|study\s+schedule|schedule|plan)"

_PLAN_PROHIBITION_PATTERNS = [
    rf"\b(?:without|avoid|skip|stop|hold\s+off\s+on)\s+(?:\w+\s+){{0,3}}?{PLAN_NOUNS}\b",
    rf"\b(?:do\s+not|don't|dont|never)\s+(?:\w+\s+){{0,4}}?{PLAN_NOUNS}(?:\s+yet)?\b",
    rf"\bno\s+{PLAN_NOUNS}(?:\s+yet)?\b",
    rf"\bnot\s+(?:want|need|asking\s+for|looking\s+for)\s+(?:a\s+|an\s+|any\s+)?{PLAN_NOUNS}(?:\s+yet)?\b",
]

_ACTIVATION_PROHIBITION_PATTERNS = [
    r"\b(?:do\s+not|don't|dont|without|never|no)\s+(?:\w+\s+){0,3}?(?:activate|activation|apply|save|persist)\b",
    r"\bdon'?t\s+activate\s+anything\b",
]

_MODIFICATION_PROHIBITION_PATTERNS = [
    r"\b(?:do\s+not|don't|dont|without|never|no)\s+(?:\w+\s+){0,4}?(?:modify|modification|change|update|overwrite|edit|alter)\b",
    r"\b(?:do\s+not|don't|dont)\s+modify\s+(?:my\s+)?(?:preparation\s+)?records\b",
]

_INVESTIGATION_ONLY_PATTERNS = [
    r"\b(?:only|just|strictly|first)\s+investigate\b",
    r"\binvestigation\s+only\b",
    r"\bonly\s+(?:analyze|assess|audit|inspect|check)\b",
]

_EXPLICIT_PLAN_AUTH_PATTERNS = [
    rf"\b(?:create|generate|build|make|design|prepare|give\s+me|need|want|adjust|modify|update|optimize|rebalance)\s+(?:\w+\s+){{0,3}}?{PLAN_NOUNS}\b",
    r"\bhow\s+should\s+i\s+prepare\b",
]

_EXPLICIT_PLAN_MOD_PATTERNS = [
    rf"\b(?:adjust|modify|update|optimize|rebalance|reschedule|revise)\s+(?:\w+\s+){{0,3}}?{PLAN_NOUNS}\b",
]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_ACTIVATION_WORDS_RE = r"\b(?:activate|activation|apply|save|persist)\b"
_MODIFICATION_WORDS_RE = r"\b(?:modify|modification|change|update|overwrite|edit|alter)\b"
_CLAUSE_SPLIT_RE = re.compile(r"[.;!?\n]+|(?:\s*,\s*(?:but|however|yet|instead)\b)|\b(?:but|however)\b")
_NEGATION_START_RE = re.compile(
    r"\b(?:do\s+not|don't|dont|never|without|avoid|skip|hold\s+off\s+on|not\s+(?:want|need|asking\s+for|looking\s+for)|no)\b"
)


def extract_action_constraints(query: str) -> tuple[WorkflowActionConstraints, str, dict[str, bool]]:
    """
    Detect explicit user prohibitions, investigation-only directives, and positive planning authorizations.
    Uses clause-scoped negation detection so multi-verb prohibitions (e.g.
    'do not create, preview, save, modify or activate any study plan') are never bypassed,
    and returns `affirmative_query` with negated spans masked out.
    """
    q = query.lower()
    masked = q
    prohibitions: list[str] = []
    reasons: list[str] = []

    plan_prohibited = False
    activation_prohibited = False
    modification_prohibited = False

    # 1. Clause-scoped negation matching (handles multi-verb lists inside one clause/sentence)
    for clause in _CLAUSE_SPLIT_RE.split(q):
        cl = clause.strip()
        if not cl:
            continue
        for m_neg in _NEGATION_START_RE.finditer(cl):
            neg_span = cl[m_neg.start():min(len(cl), m_neg.start() + 120)]
            matched_tail_end = None
            has_plan = False
            has_act = False
            has_mod = False

            for m_p in re.finditer(PLAN_NOUNS, neg_span):
                has_plan = True
                matched_tail_end = max(matched_tail_end or 0, m_p.end())
            for m_a in re.finditer(_ACTIVATION_WORDS_RE, neg_span):
                # Avoid false match on "no ..." unrelated nouns unless after negation verb, OK for activate/save/persist
                if re.match(r"^no\b", neg_span) and m_a.group(0) in ("apply",):
                    continue
                has_act = True
                matched_tail_end = max(matched_tail_end or 0, m_a.end())
            for m_m in re.finditer(_MODIFICATION_WORDS_RE, neg_span):
                has_mod = True
                matched_tail_end = max(matched_tail_end or 0, m_m.end())
            if re.search(r"\banything\b", neg_span) and re.search(_ACTIVATION_WORDS_RE, neg_span):
                has_act = True

            if matched_tail_end:
                phrase = neg_span[:matched_tail_end].strip()
                if has_plan:
                    plan_prohibited = True
                if has_act:
                    activation_prohibited = True
                if has_mod:
                    modification_prohibited = True
                if phrase and phrase not in prohibitions:
                    prohibitions.append(phrase)
                masked = masked.replace(phrase, " ")

    # 2. Run explicit short-span regexes as reinforcement for any edge phrasing
    for pat in _PLAN_PROHIBITION_PATTERNS:
        for m in re.finditer(pat, q):
            plan_prohibited = True
            phrase = m.group(0).strip()
            if phrase not in prohibitions:
                prohibitions.append(phrase)
            masked = masked.replace(phrase, " ")
    if plan_prohibited:
        reasons.append("User explicitly prohibited study plan/timetable generation.")

    for pat in _ACTIVATION_PROHIBITION_PATTERNS:
        for m in re.finditer(pat, q):
            activation_prohibited = True
            phrase = m.group(0).strip()
            if phrase not in prohibitions:
                prohibitions.append(phrase)
            masked = masked.replace(phrase, " ")
    if activation_prohibited:
        reasons.append("User explicitly prohibited plan activation/application.")

    for pat in _MODIFICATION_PROHIBITION_PATTERNS:
        for m in re.finditer(pat, q):
            modification_prohibited = True
            phrase = m.group(0).strip()
            if phrase not in prohibitions:
                prohibitions.append(phrase)
            masked = masked.replace(phrase, " ")
    if modification_prohibited:
        reasons.append("User explicitly prohibited record modification.")

    investigation_only = False
    for pat in _INVESTIGATION_ONLY_PATTERNS:
        m = re.search(pat, q)
        if m:
            investigation_only = True
            phrase = m.group(0).strip()
            if phrase not in prohibitions:
                prohibitions.append(phrase)
    if investigation_only:
        reasons.append("User requested investigation/analysis only.")

    explicit_plan_request = any(re.search(pat, masked) for pat in _EXPLICIT_PLAN_AUTH_PATTERNS)
    explicit_plan_modify = any(re.search(pat, masked) for pat in _EXPLICIT_PLAN_MOD_PATTERNS)

    conflicting_plan_request = plan_prohibited and explicit_plan_request
    if conflicting_plan_request:
        reasons.append(
            "Conflicting directives detected (simultaneous prohibition and request for a study plan/timetable); "
            "enforcing the explicit prohibition."
        )

    # Hours-based transition/preparation prompt without prohibitions or feasibility-only framing
    has_hours = bool(re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)", masked))
    feasibility_framing = any(
        k in masked for k in ["feasible", "feasibility", "insufficient", "realistically aligned", "enough time", "worried"]
    )
    hours_implies_schedule = has_hours and not feasibility_framing and not plan_prohibited and not investigation_only

    plan_gen_allowed = (explicit_plan_request or explicit_plan_modify or hours_implies_schedule) and not plan_prohibited and not investigation_only
    plan_preview_allowed = plan_gen_allowed
    plan_activation_allowed = plan_gen_allowed and not activation_prohibited and not modification_prohibited
    modification_allowed = plan_activation_allowed and not modification_prohibited and not investigation_only

    constraints = WorkflowActionConstraints(
        plan_generation_allowed=plan_gen_allowed,
        plan_preview_allowed=plan_preview_allowed,
        plan_activation_allowed=plan_activation_allowed,
        assessment_generation_allowed=False,
        modification_allowed=modification_allowed,
        investigation_only=investigation_only or (plan_prohibited and not explicit_plan_request),
        explicit_user_prohibitions=prohibitions,
        prohibition_reasons=reasons,
    )
    flags = {
        "plan_prohibited": plan_prohibited,
        "activation_prohibited": activation_prohibited,
        "modification_prohibited": modification_prohibited,
        "investigation_only": investigation_only,
        "explicit_plan_request": explicit_plan_request,
        "explicit_plan_modify": explicit_plan_modify,
        "conflicting_plan_request": conflicting_plan_request,
    }
    return constraints, masked, flags


def _detect_exams_and_unsupported(
    query: str,
    valid_exam_ids: set[str],
    default_primary: str,
) -> tuple[list[str], list[str]]:
    q = query.lower()
    matched_positions: list[tuple[int, str]] = []
    for ex_id, aliases in EXAM_ALIASES.items():
        if ex_id not in valid_exam_ids:
            continue
        earliest = None
        for kw in aliases:
            m = re.search(rf"\b{re.escape(kw)}\b", q)
            if m:
                if earliest is None or m.start() < earliest:
                    earliest = m.start()
        if earliest is not None:
            matched_positions.append((earliest, ex_id))

    matched_positions.sort(key=lambda pair: pair[0])
    found: list[str] = []
    for _, ex_id in matched_positions:
        if ex_id not in found:
            found.append(ex_id)

    unsupported: list[str] = []
    for hint in UNSUPPORTED_EXAM_HINTS:
        if re.search(rf"\b{re.escape(hint)}\b", q):
            unsupported.append(hint.upper())

    if not found and not unsupported:
        found.append(default_primary if default_primary in valid_exam_ids else sorted(valid_exam_ids)[0])
    return found, unsupported


def _extract_constraints(query: str, valid_subject_ids: set[str]) -> PreparationConstraints:
    q = query.lower()
    hours = None
    m_hrs = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)(?:\s*(?:per|a|/)\s*day)?", q)
    if m_hrs:
        hours = max(0.5, min(16.0, float(m_hrs.group(1))))

    days = None
    m_days = re.search(r"(\d+)\s*days?\s*(?:per|a|/)\s*week", q)
    if m_days:
        days = max(1, min(7, int(m_days.group(1))))

    months = None
    m_months = re.search(r"(\d+)\s*months?", q)
    if m_months:
        months = max(1, min(60, int(m_months.group(1))))
    else:
        m_yrs = re.search(r"(\d+)\s*years?", q)
        if m_yrs:
            months = max(1, min(60, int(m_yrs.group(1)) * 12))

    subject_keywords = {
        "POLITY": ["polity", "constitution", "parliament", "judiciary", "governance"],
        "ECONOMY": ["economy", "economics", "fiscal", "monetary", "banking", "gdp"],
        "HISTORY": ["history", "freedom struggle", "culture", "ancient", "medieval", "modern"],
        "GEOGRAPHY": ["geography", "environment", "ecology", "climate"],
        "SCIENCE_TECH": ["science", "technology", "physics", "biology", "space"],
        "CURRENT_AFFAIRS": ["current affairs", "schemes", "international relations"],
        "QUANT": ["quantitative", "quant", "aptitude", "maths", "arithmetic", "math"],
        "REASONING": ["reasoning", "logical", "puzzles", "syllogism"],
        "ENGLISH": ["english", "grammar", "comprehension"],
        "STATE_TN": ["tamil nadu", "unit 8", "unit 9", "thirukkural", "sangam"],
    }
    focus_subjects = [
        sid for sid, kws in subject_keywords.items()
        if sid in valid_subject_ids and any(re.search(rf"\b{re.escape(k)}\b", q) for k in kws)
    ]

    return PreparationConstraints(
        daily_hours=hours,
        days_per_week=days,
        timeline_months=months,
        focus_subjects=focus_subjects,
    )


def _normalize_plan(
    plan: StructuredPlan,
    valid_exam_ids: set[str],
    default_primary: str,
    registry: ToolRegistry,
    det_constraints: WorkflowActionConstraints,
    det_flags: dict[str, bool],
) -> StructuredPlan:
    valid_mentioned = [eid for eid in plan.mentioned_examinations if eid in valid_exam_ids]
    primary = plan.primary_examination if plan.primary_examination in valid_exam_ids else None
    target = plan.target_or_alternative_examination if plan.target_or_alternative_examination in valid_exam_ids else None

    if primary and primary not in valid_mentioned:
        valid_mentioned.insert(0, primary)
    if target and target not in valid_mentioned:
        valid_mentioned.append(target)

    if not valid_mentioned and not plan.missing_information:
        fallback_exam = default_primary if default_primary in valid_exam_ids else sorted(valid_exam_ids)[0]
        valid_mentioned = [fallback_exam]
        primary = fallback_exam

    if not primary and valid_mentioned:
        primary = valid_mentioned[0]

    # Enforce deterministic prohibition guardrails over LLM plans too
    merged = plan.action_constraints.model_copy()
    if det_flags["plan_prohibited"] or det_flags["investigation_only"]:
        merged.plan_generation_allowed = False
        merged.plan_preview_allowed = False
        merged.plan_activation_allowed = False
        merged.investigation_only = True
    elif plan.query_category in ("study_plan_generation", "study_plan_modification", "study_plan_optimization"):
        merged.plan_generation_allowed = True
        merged.plan_preview_allowed = True
        merged.plan_activation_allowed = not det_flags["activation_prohibited"] and not det_flags["modification_prohibited"]
        merged.investigation_only = False
    elif det_constraints.plan_generation_allowed and (
        "StudyOptimizationAgent" in plan.required_agents
        or det_flags["explicit_plan_request"]
        or (
            plan.preparation_constraints.daily_hours is not None
            and plan.query_category not in (
                "preparation_evidence_investigation",
                "preparation_feasibility_analysis",
                "diagnostic_assessment_recommendation",
            )
        )
    ):
        merged.plan_generation_allowed = True
        merged.plan_preview_allowed = True
        merged.plan_activation_allowed = det_constraints.plan_activation_allowed
        merged.investigation_only = False
        if "StudyOptimizationAgent" not in plan.required_agents:
            plan.required_agents.append("StudyOptimizationAgent")
    else:
        merged.plan_generation_allowed = merged.plan_generation_allowed and det_constraints.plan_generation_allowed
        merged.plan_preview_allowed = merged.plan_preview_allowed and det_constraints.plan_preview_allowed
        merged.plan_activation_allowed = (
            merged.plan_activation_allowed
            and det_constraints.plan_activation_allowed
            and not det_flags["activation_prohibited"]
        )

    if det_flags["activation_prohibited"]:
        merged.plan_activation_allowed = False
    if det_flags["modification_prohibited"]:
        merged.modification_allowed = False
        merged.plan_activation_allowed = False

    merged.explicit_user_prohibitions = list(
        dict.fromkeys(list(det_constraints.explicit_user_prohibitions) + list(merged.explicit_user_prohibitions))
    )
    merged.prohibition_reasons = list(
        dict.fromkeys(list(det_constraints.prohibition_reasons) + list(merged.prohibition_reasons))
    )

    # Filter tools strictly against ToolRegistry allowlist AND action constraints
    approved_tools = [t for t in plan.required_tools if registry.is_allowed(t)]
    if not merged.plan_generation_allowed or not merged.plan_preview_allowed:
        approved_tools = [t for t in approved_tools if t != "generate_study_plan_preview"]

    seen_tools: set[str] = set()
    clean_tools: list[str] = []
    for t in approved_tools:
        if t not in seen_tools:
            seen_tools.add(t)
            clean_tools.append(t)

    seen_agents: set[str] = set()
    clean_agents: list[AgentName] = []
    for ag in plan.required_agents:
        if ag == "StudyOptimizationAgent" and not merged.plan_generation_allowed:
            continue
        if ag in VALID_AGENTS and ag not in seen_agents:
            seen_agents.add(ag)
            clean_agents.append(ag)

    if not clean_agents:
        clean_agents = ["StudentAnalysisAgent"]

    if plan.query_category in ("preparation_feasibility_analysis", "preparation_time_feasibility") and "PathwayPlanningAgent" not in clean_agents:
        clean_agents.append("PathwayPlanningAgent")
        if "simulate_preparation_constraints" not in clean_tools:
            clean_tools.append("simulate_preparation_constraints")
        plan.selection_rationale.setdefault(
            "PathwayPlanningAgent",
            "Evaluate preparation time and workload feasibility against target exam requirements.",
        )

    plan.primary_examination = primary
    plan.target_or_alternative_examination = target
    plan.mentioned_examinations = valid_mentioned
    plan.action_constraints = merged
    plan.required_tools = clean_tools
    plan.required_agents = clean_agents
    if not plan.execution_sequence:
        plan.execution_sequence = list(clean_agents)
    else:
        plan.execution_sequence = [a for a in plan.execution_sequence if a in clean_agents]
        if not plan.execution_sequence:
            plan.execution_sequence = list(clean_agents)
    return plan


def build_fallback_plan(
    db: Session,
    user_id: int,
    query: str,
    registry: ToolRegistry,
    planner_error: Optional[str] = None,
) -> StructuredPlan:
    """
    Prohibition-aware deterministic fallback planner when external LLM is unavailable,
    fails, or returns malformed output. Explicitly marks planner_mode='deterministic_fallback'.
    """
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    default_primary = profile.primary_target_exam if profile else "UPSC_CSE"
    valid_exam_ids = {e.id for e in db.query(Exam).all()}
    valid_subject_ids = {s.id for s in db.query(Subject).all()}

    action_constraints, affirmative_q, flags = extract_action_constraints(query)
    mentioned, unsupported = _detect_exams_and_unsupported(query, valid_exam_ids, default_primary)
    constraints = _extract_constraints(query, valid_subject_ids)

    if unsupported:
        return StructuredPlan(
            user_objective=f"Address query mentioning unsupported examination(s): {', '.join(unsupported)}",
            query_category="exam_information_retrieval",
            primary_examination=default_primary if default_primary in valid_exam_ids else None,
            mentioned_examinations=[],
            preparation_constraints=constraints,
            action_constraints=action_constraints,
            requested_analysis=["exam_catalogue_check"],
            required_agents=["ExamIntelligenceAgent"],
            selection_rationale={"ExamIntelligenceAgent": "Check supported examination catalogue for unsupported exam query."},
            required_tools=["get_exam_catalogue"],
            execution_sequence=["ExamIntelligenceAgent"],
            missing_information=[
                f"Examinations {', '.join(unsupported)} are outside the supported Indian government examination catalogue."
            ],
            clarification_required=True,
            clarification_question=(
                f"GovPath AI currently supports {', '.join(sorted(valid_exam_ids))}. "
                f"Would you like analysis for one of these supported examinations instead?"
            ),
            requires_verified_exam_info=True,
            planner_mode="deterministic_fallback",
            planner_provider="deterministic_fallback",
            planner_error=planner_error,
            confidence=0.85,
            decision_summary="Detected unsupported exam reference; checking supported exam catalogue only.",
        )

    # Detect workflow intents on affirmative_q (negated/prohibited clauses already masked out!)
    wants_evidence_inv = any(
        k in affirmative_q
        for k in [
            "stored preparation",
            "preparation records",
            "stored records",
            "which evidence",
            "available evidence",
            "insufficient evidence",
            "missing evidence",
            "have evidence for",
            "what evidence supports",
            "only investigate",
            "investigate my",
            "audit my preparation",
        ]
    )
    wants_next_assessment = any(
        k in affirmative_q
        for k in [
            "what assessment",
            "which assessment",
            "next assessment",
            "most useful to take next",
            "which quiz",
            "which test should i take",
            "what should i assess",
            "assess next",
            "focus on next",
            "prioritize next",
        ]
    )
    wants_feasibility = any(
        k in affirmative_q
        for k in [
            "feasible",
            "feasibility",
            "insufficient time",
            "time left is insufficient",
            "amount of time",
            "time i have left",
            "realistically aligned",
            "realistic",
            "enough time",
            "can i complete",
            "worried",
        ]
    ) or bool(re.search(r"\b(?:time|hours?|months?|days?)\b.{0,30}\binsufficient\b", affirmative_q)) or (
        (constraints.daily_hours is not None or constraints.timeline_months is not None)
        and not action_constraints.plan_generation_allowed
    )

    wants_transfer = (
        any(
            k in affirmative_q
            for k in [
                "transfer",
                "overlap",
                "switch",
                "move from",
                "without starting from zero",
                "bridge",
                "useful for",
                "shared between",
                "shared competencies",
                "additional skills",
            ]
        )
        or len(mentioned) >= 2
    )
    exam_compare_context = len(mentioned) >= 2 or bool(
        re.search(r"\b(?:exams?|examinations?|syllab(?:us|i)|patterns?|pathways?|options?|between)\b", affirmative_q)
    )
    wants_compare = exam_compare_context and any(
        k in affirmative_q for k in ["compare", "difference", "vs", "versus"]
    )
    wants_diagnosis = (
        any(
            k in affirmative_q
            for k in [
                "weakness",
                "weaknesses",
                "losing marks",
                "mistake",
                "mistakes",
                "error",
                "errors",
                "wrong",
                "diagnosis",
                "accuracy",
                "struggling",
                "weak areas",
                "weak in",
                "weak competencies",
            ]
        )
        or ("weak" in affirmative_q and not flags["explicit_plan_request"] and not wants_evidence_inv)
    )
    wants_retention = any(
        k in affirmative_q for k in ["forget", "forgetting", "retention", "revise", "revision", "recall", "last month"]
    )
    wants_pathway = any(
        k in affirmative_q for k in ["pathway", "which exam", "backup", "alternative", "decide", "career", "switch"]
    )
    wants_progress = any(
        k in affirmative_q
        for k in [
            "progress",
            "how am i doing",
            "tasks completed",
            "study activity",
            "track my",
            "previous performance",
            "recent preparation",
            "recent assessment performance",
            "recent performance",
            "improving or stagnating",
            "stagnating",
            "improving or",
        ]
    )
    wants_plan_review = any(
        k in affirmative_q
        for k in [
            "current study plan",
            "existing study plan",
            "existing plan",
            "current plan",
            "proposed study plan",
            "my study plan",
        ]
    )
    wants_exam_info = any(
        k in affirmative_q
        for k in ["syllabus", "pattern", "eligibility", "stages", "exam date", "notification", "vacancy", "vacancies", "cutoff"]
    )
    wants_readiness = any(
        k in affirmative_q
        for k in [
            "readiness",
            "ready",
            "gap",
            "gaps",
            "score",
            "aligned with my goal",
            "aligned with my exam goal",
            "preparation aligned",
            "preparation level",
            "current level",
            "assess my",
            "where do i stand",
        ]
    )
    wants_dates = any(
        k in affirmative_q for k in ["exam date", "notification date", "last date", "vacancy", "vacancies", "cutoff 202"]
    )

    # Determine workflow categories without double-counting sub-tasks of a unified workflow
    categories: list[IntentCategory] = []

    if wants_transfer:
        categories.append("competency_transfer_analysis")
    elif wants_compare and not wants_pathway and not wants_progress:
        categories.append("examination_comparison")

    if wants_feasibility:
        categories.append("preparation_feasibility_analysis")

    if wants_evidence_inv and not wants_transfer and not wants_feasibility and not flags["explicit_plan_request"]:
        categories.append("preparation_evidence_investigation")
    elif wants_next_assessment and not wants_evidence_inv and not wants_diagnosis and not wants_progress:
        categories.append("diagnostic_assessment_recommendation")

    if wants_diagnosis and not wants_evidence_inv:
        categories.append("performance_diagnosis")
    if wants_retention:
        categories.append("retention_analysis")
    if wants_pathway and not wants_feasibility:
        categories.append("alternative_examination_pathway")
    if action_constraints.plan_generation_allowed:
        categories.append("study_plan_modification" if flags["explicit_plan_modify"] else "study_plan_generation")
    if wants_progress and not wants_evidence_inv and not flags["explicit_plan_request"]:
        categories.append("progress_monitoring")
    if wants_exam_info and not wants_transfer:
        categories.append("exam_information_retrieval")
    if wants_readiness and not wants_evidence_inv and not wants_feasibility and not wants_transfer and not flags["explicit_plan_request"]:
        categories.append("readiness_evaluation")

    word_count = len(re.findall(r"\w+", affirmative_q))
    is_ambiguous = word_count <= 2 and not categories

    if len(categories) >= 2:
        primary_cat: IntentCategory = "compound_multi_intent"
        secondary_cats = [c for c in categories if c != primary_cat][:4]
    elif len(categories) == 1:
        primary_cat = categories[0]
        secondary_cats = []
    else:
        primary_cat = "general_counselling"
        secondary_cats = []

    # Dynamic, minimal agent & tool selection
    agents: list[AgentName] = ["StudentAnalysisAgent"]
    rationale: dict[str, str] = {
        "StudentAnalysisAgent": "Retrieve stored profile, preparation constraints, readiness alignment, and competency evidence records."
    }
    tools: list[str] = [
        "get_aspirant_profile",
        "get_preparation_constraints",
        "get_student_readiness",
        "get_competency_evidence",
        "get_preparation_progress",
    ]

    if wants_retention or wants_evidence_inv or wants_progress or wants_plan_review or primary_cat in ("study_plan_generation", "study_plan_modification"):
        tools.append("get_retention_status")

    if (
        wants_next_assessment
        or wants_evidence_inv
        or wants_progress
        or wants_diagnosis
        or wants_plan_review
        or primary_cat in ("diagnostic_assessment_recommendation", "readiness_evaluation", "progress_monitoring")
    ):
        tools.append("recommend_next_assessment")

    if wants_plan_review:
        tools.append("get_existing_study_tasks")

    needs_exam_intel = (
        wants_exam_info
        or wants_transfer
        or wants_compare
        or wants_feasibility
        or wants_pathway
        or wants_dates
        or action_constraints.plan_generation_allowed
    )
    if needs_exam_intel:
        agents.append("ExamIntelligenceAgent")
        rationale["ExamIntelligenceAgent"] = "Retrieve verified exam framework, competency requirements, and syllabus context."
        tools.extend(["get_exam_structure", "get_exam_syllabus", "search_exam_documents"])
        if wants_dates:
            tools.append("get_official_exam_sources")

    if wants_diagnosis or wants_retention:
        agents.append("PerformanceDiagnosisAgent")
        rationale["PerformanceDiagnosisAgent"] = "Diagnose answer-level error categories and repeated weak competencies."
        tools.extend(["diagnose_assessment_errors", "get_weak_competencies"])

    if wants_transfer or wants_compare:
        agents.append("KnowledgeTransferAgent")
        rationale["KnowledgeTransferAgent"] = "Compare shared competencies, target-only gaps, and evidence-disclosed transferability."
        tools.append("calculate_transferability")
        if len(mentioned) > 2 or wants_compare:
            tools.append("compare_exams")

    if wants_feasibility or wants_pathway or (wants_transfer and "switch" in affirmative_q):
        agents.append("PathwayPlanningAgent")
        rationale["PathwayPlanningAgent"] = (
            "Evaluate time/workload feasibility against target competency gaps and constraints."
            if wants_feasibility
            else "Evaluate alternative examination pathways and workload simulation."
        )
        if wants_feasibility:
            tools.append("simulate_preparation_constraints")
        else:
            tools.append("get_pathway_recommendations")
            if constraints.daily_hours is not None or "switch" in affirmative_q:
                tools.append("simulate_preparation_constraints")

    if action_constraints.plan_generation_allowed:
        agents.append("StudyOptimizationAgent")
        rationale["StudyOptimizationAgent"] = "Generate an adaptive weekly study plan preview under validated constraints."
        tools.extend(["generate_study_plan_preview", "get_existing_study_tasks"])

    primary_exam = mentioned[0] if mentioned else default_primary
    target_exam: Optional[str] = None
    if len(mentioned) >= 2:
        target_exam = mentioned[1]
    elif wants_transfer or wants_compare:
        target_exam = "TNPSC_GRP1" if primary_exam != "TNPSC_GRP1" else "SSC_CGL"
        if target_exam in valid_exam_ids and target_exam not in mentioned:
            mentioned.append(target_exam)

    missing_info: list[str] = []
    if wants_dates:
        missing_info.append("Live cycle dates, vacancies, and notification cutoffs are not stored locally and require official portal verification.")
    if is_ambiguous:
        missing_info.append("User query is brief/underspecified; clarify specific target exam, weakness, or investigation goal.")

    plan = StructuredPlan(
        user_objective=sanitize_user_query(query, max_len=300),
        query_category=primary_cat,
        secondary_categories=secondary_cats,
        primary_examination=primary_exam,
        target_or_alternative_examination=target_exam,
        mentioned_examinations=mentioned,
        relevant_competencies=constraints.focus_subjects,
        preparation_constraints=constraints,
        action_constraints=action_constraints,
        requested_analysis=[str(c) for c in (categories or ["general_counselling"])],
        required_agents=agents,
        selection_rationale=rationale,
        required_tools=tools,
        execution_sequence=list(agents),
        missing_information=missing_info,
        clarification_required=is_ambiguous,
        clarification_question=(
            "Could you clarify whether you want an evidence audit, feasibility evaluation, exam transfer comparison, or study plan adjustment?"
            if is_ambiguous else None
        ),
        requires_verified_exam_info=wants_exam_info or wants_dates,
        planner_mode="deterministic_fallback",
        planner_provider="deterministic_fallback",
        planner_error=planner_error,
        confidence=0.55 if is_ambiguous else 0.82,
        decision_summary=f"Deterministic fallback selected workflow '{primary_cat}' with {len(agents)} agent(s).",
    )
    return _normalize_plan(plan, valid_exam_ids, default_primary, registry, action_constraints, flags)


def plan_user_query(
    db: Session,
    user_id: int,
    query: str,
    registry: ToolRegistry,
    state: Optional[OrchestrationState] = None,
    conversation_context: Optional[list[dict[str, str]]] = None,
) -> StructuredPlan:
    """
    Create a validated StructuredPlan using the configured server-side LLM when available,
    with strict enforcement of user prohibitions and safe deterministic fallback on failure/unavailability.
    """
    settings = get_settings()
    clean_query = sanitize_user_query(query)
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    default_primary = profile.primary_target_exam if profile else "UPSC_CSE"
    exams = db.query(Exam).all()
    valid_exam_ids = {e.id for e in exams}

    det_constraints, _, det_flags = extract_action_constraints(clean_query)

    execution_id = f"plan_{uuid.uuid4().hex[:8]}"
    step_order = (len(state.tool_execution_records) + 1) if state else 1
    started_iso = _utc_iso()

    llm_status = get_llm_status()
    can_use_llm = (
        llm_status["configured"]
        and (state is None or state.llm_calls_used < settings.ORCHESTRATOR_MAX_LLM_CALLS)
        and (state is None or state.estimated_tokens_used < settings.ORCHESTRATOR_TOKEN_BUDGET)
    )

    if not can_use_llm:
        plan = build_fallback_plan(db, user_id, clean_query, registry)
        if state is not None:
            state.fallback_used = True
            state.tool_execution_records.append(
                ToolExecutionRecord(
                    execution_id=execution_id,
                    step_order=step_order,
                    kind="planner",
                    agent="Intent & Workflow Planner",
                    tool="deterministic_fallback_planner",
                    status="completed",
                    input_summary=clean_query[:160],
                    output_summary=f"mode={plan.planner_mode}, workflow={plan.query_category}, agents={plan.required_agents}",
                    started_at=started_iso,
                    ended_at=_utc_iso(),
                    duration_ms=0.0,
                    metadata={
                        "planner_mode": plan.planner_mode,
                        "workflow": plan.query_category,
                        "prohibitions": plan.action_constraints.explicit_user_prohibitions,
                    },
                )
            )
        return plan

    exam_catalog_text = "\n".join(f"- {e.id}: {e.name} ({e.short_name})" for e in exams)
    tools_text = "\n".join(
        f"- {t['name']} [{t['category']}]: {t['description']}"
        for t in registry.describe_tools_for_planner()
    )
    history_text = ""
    if conversation_context:
        recent = conversation_context[-4:]
        history_text = "\nRecent conversation context:\n" + "\n".join(
            f"- {m.get('role', 'user')}: {sanitize_user_query(m.get('content', ''), 200)}"
            for m in recent
        )

    system_prompt = (
        "You are the Structured Intent & Workflow Planner for GovPath AI, an Indian government exam preparation system.\n"
        "Analyze the aspirant's query and output ONLY valid JSON matching the exact schema below.\n"
        "RULES:\n"
        "1. Select ONLY the agents and tools genuinely needed for the user's objective — do NOT select all agents unnecessarily.\n"
        "2. Strictly respect negative constraints and prohibitions (e.g., 'without creating a study plan', "
        "'do not want a timetable yet', 'don't activate anything', 'only investigate', 'do not modify records'). "
        "When study plans/timetables are prohibited or investigation-only is requested, set action_constraints.plan_generation_allowed=false, "
        "plan_preview_allowed=false, plan_activation_allowed=false, investigation_only=true, and NEVER select StudyOptimizationAgent or generate_study_plan_preview. "
        "Conversely, when the user asks to create/adjust a study plan or transition with explicit daily study hours without prohibiting planning, "
        "include StudyOptimizationAgent and set plan_generation_allowed=true, plan_preview_allowed=true, plan_activation_allowed=true.\n"
        "3. Use ONLY valid exam IDs from the provided catalogue.\n"
        "4. Use ONLY tool names from the provided Approved Tool Registry.\n"
        "5. Allowed agent names: StudentAnalysisAgent, ExamIntelligenceAgent, PerformanceDiagnosisAgent, "
        "KnowledgeTransferAgent, PathwayPlanningAgent, StudyOptimizationAgent.\n"
        "6. Preferred query_category values: preparation_evidence_investigation, preparation_feasibility_analysis, "
        "competency_transfer_analysis, diagnostic_assessment_recommendation, study_plan_generation, "
        "study_plan_modification, progress_monitoring, exam_information_retrieval, compound_multi_intent, "
        "readiness_evaluation, performance_diagnosis, competency_gap_analysis, retention_analysis, "
        "knowledge_transfer, examination_comparison, alternative_examination_pathway, general_counselling.\n"
        "7. JSON fields: user_objective (str), query_category (str), secondary_categories (list[str], [] if none), "
        "primary_examination (str|null), target_or_alternative_examination (str|null), mentioned_examinations (list[str]), "
        "relevant_competencies (list[str], [] if none), preparation_constraints ({daily_hours, days_per_week, timeline_months, focus_subjects: list[str], notes: str}), "
        "action_constraints ({plan_generation_allowed: bool, plan_preview_allowed: bool, plan_activation_allowed: bool, assessment_generation_allowed: bool, modification_allowed: bool, investigation_only: bool, explicit_user_prohibitions: list[str] ([] if none), prohibition_reasons: list[str] ([] if none)}), "
        "requested_analysis (list[str]), required_agents (list[str]), selection_rationale (dict[str,str]), required_tools (list[str]), "
        "execution_sequence (list[str]), missing_information (list[str]), clarification_required (bool), "
        "clarification_question (str|null), requires_verified_exam_info (bool), confidence (float 0..1), decision_summary (str)."
    )

    user_prompt = (
        f"Aspirant profile context: primary_target_exam={default_primary}, "
        f"daily_study_hours={profile.daily_study_hours if profile else 4.5}, "
        f"days_per_week={profile.days_per_week if profile else 6}, "
        f"timeline_months={profile.timeline_months if profile else 12}.\n\n"
        f"Supported Examinations:\n{exam_catalog_text}\n\n"
        f"Approved Tool Registry:\n{tools_text}\n"
        f"{history_text}\n\n"
        f"Current User Query: {clean_query}"
    )

    llm_res = generate_structured_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_model=StructuredPlan,
        temperature=0.1,
        max_tokens=1000,
    )
    if state is not None:
        state.llm_calls_used += 1
        state.estimated_tokens_used += llm_res.tokens_used

    if llm_res.ok and isinstance(llm_res.data, StructuredPlan):
        plan = llm_res.data
        valid_subject_ids = {s.id for s in db.query(Subject).all()}
        det_prep = _extract_constraints(clean_query, valid_subject_ids)
        if plan.preparation_constraints.daily_hours is None and det_prep.daily_hours is not None:
            plan.preparation_constraints.daily_hours = det_prep.daily_hours
        if plan.preparation_constraints.days_per_week is None and det_prep.days_per_week is not None:
            plan.preparation_constraints.days_per_week = det_prep.days_per_week
        if plan.preparation_constraints.timeline_months is None and det_prep.timeline_months is not None:
            plan.preparation_constraints.timeline_months = det_prep.timeline_months
        if not plan.preparation_constraints.focus_subjects and det_prep.focus_subjects:
            plan.preparation_constraints.focus_subjects = det_prep.focus_subjects

        plan.planner_mode = "llm_structured"
        plan.planner_provider = f"{llm_res.provider}:{llm_res.model}"
        plan.planner_error = None
        plan = _normalize_plan(plan, valid_exam_ids, default_primary, registry, det_constraints, det_flags)

        if state is not None:
            state.tool_execution_records.append(
                ToolExecutionRecord(
                    execution_id=execution_id,
                    step_order=step_order,
                    kind="planner",
                    agent="Intent & Workflow Planner",
                    tool=f"llm_structured_planner({llm_res.provider})",
                    status="completed",
                    input_summary=clean_query[:160],
                    output_summary=f"mode=llm_structured, workflow={plan.query_category}, agents={plan.required_agents}",
                    started_at=started_iso,
                    ended_at=_utc_iso(),
                    duration_ms=llm_res.latency_ms,
                    metadata={
                        "planner_mode": plan.planner_mode,
                        "workflow": plan.query_category,
                        "prohibitions": plan.action_constraints.explicit_user_prohibitions,
                    },
                )
            )
        return plan

    err_msg = llm_res.error or "LLM planner returned invalid output"
    plan = build_fallback_plan(db, user_id, clean_query, registry, planner_error=err_msg)
    if state is not None:
        state.fallback_used = True
        state.llm_error = err_msg
        state.errors.append(f"LLM planner fallback triggered ({llm_res.provider}): {err_msg}")
        state.tool_execution_records.append(
            ToolExecutionRecord(
                execution_id=execution_id,
                step_order=step_order,
                kind="planner",
                agent="Intent & Workflow Planner",
                tool=f"llm_structured_planner({llm_res.provider})",
                status="failed",
                input_summary=clean_query[:160],
                started_at=started_iso,
                ended_at=_utc_iso(),
                duration_ms=llm_res.latency_ms,
                error_details=err_msg,
            )
        )
        state.tool_execution_records.append(
            ToolExecutionRecord(
                execution_id=f"plan_fb_{uuid.uuid4().hex[:6]}",
                step_order=step_order + 1,
                kind="planner",
                agent="Intent & Workflow Planner",
                tool="deterministic_fallback_planner",
                status="completed",
                input_summary=clean_query[:160],
                output_summary=f"mode=deterministic_fallback, workflow={plan.query_category}, agents={plan.required_agents}",
                started_at=_utc_iso(),
                ended_at=_utc_iso(),
                duration_ms=0.0,
                metadata={
                    "planner_mode": plan.planner_mode,
                    "workflow": plan.query_category,
                    "prohibitions": plan.action_constraints.explicit_user_prohibitions,
                },
            )
        )
    return plan


def evaluate_evidence_and_plan_followup(
    state: OrchestrationState,
    registry: ToolRegistry,
) -> FollowUpDecision:
    """
    Evaluate gathered evidence after an execution iteration and determine whether
    additional bounded agent/tool calls are justified while respecting action constraints.
    """
    settings = get_settings()
    plan = state.structured_intent
    executed_agents = set(state.agent_outputs.keys())

    if state.execution_iteration >= settings.ORCHESTRATOR_MAX_ITERATIONS:
        return FollowUpDecision(
            sufficient_evidence=True,
            decision_summary="Reached maximum orchestration iterations.",
            stop_reason="max_iterations_reached",
        )
    if state.tool_calls_used >= settings.ORCHESTRATOR_MAX_TOOL_CALLS:
        return FollowUpDecision(
            sufficient_evidence=True,
            decision_summary="Reached maximum tool call limit.",
            stop_reason="max_tool_calls_reached",
        )
    if plan and plan.clarification_required and plan.missing_information and "unsupported" in " ".join(plan.missing_information).lower():
        return FollowUpDecision(
            sufficient_evidence=True,
            missing_evidence=list(plan.missing_information),
            decision_summary="Unsupported examination requested; stopping after catalogue verification.",
            stop_reason="unsupported_exam",
        )

    det_additional_agents: list[AgentName] = []
    det_additional_tools: list[str] = []
    missing: list[str] = []

    sa_data = state.agent_outputs.get("StudentAnalysisAgent", {}).get("data", {})
    if sa_data:
        readiness = sa_data.get("readiness", {})
        if readiness.get("assessments_completed", 0) == 0:
            missing.append(
                "Zero completed assessments recorded; measured performance evidence is unavailable and untested competencies are not verified."
            )

        ret = sa_data.get("retention", {})
        overdue_cnt = ret.get("summary", {}).get("overdue_count", 0) if isinstance(ret, dict) else 0
        declining_cnt = len(ret.get("declining_items", [])) if isinstance(ret, dict) else 0
        assessments_done = int(readiness.get("assessments_completed", 0))
        req_cats = set([plan.query_category] + list(plan.secondary_categories)) if plan else set()
        plan_review_req = bool(plan and "get_existing_study_tasks" in plan.required_tools)
        if (
            assessments_done > 0
            and (overdue_cnt > 0 or declining_cnt > 0)
            and (req_cats.intersection({"retention_analysis", "performance_diagnosis", "progress_monitoring"}) or plan_review_req)
            and "PerformanceDiagnosisAgent" not in executed_agents
        ):
            det_additional_agents.append("PerformanceDiagnosisAgent")
            det_additional_tools.append("diagnose_assessment_errors")
        elif (
            assessments_done > 0
            and float(readiness.get("accuracy", 100.0)) < 65.0
            and (req_cats.intersection({"preparation_evidence_investigation", "readiness_evaluation", "progress_monitoring"}) or plan_review_req)
            and "PerformanceDiagnosisAgent" not in executed_agents
        ):
            det_additional_agents.append("PerformanceDiagnosisAgent")
            det_additional_tools.append("diagnose_assessment_errors")

    if (
        "StudyOptimizationAgent" in executed_agents
        and "PathwayPlanningAgent" not in executed_agents
        and plan
        and (plan.preparation_constraints.daily_hours is not None or plan.preparation_constraints.timeline_months is not None)
        and plan.query_category in ("study_plan_generation", "study_plan_modification", "study_plan_optimization", "preparation_feasibility_analysis", "compound_multi_intent")
    ):
        det_additional_agents.append("PathwayPlanningAgent")
        det_additional_tools.append("simulate_preparation_constraints")

    llm_status = get_llm_status()
    if (
        llm_status["configured"]
        and not state.fallback_used
        and state.llm_calls_used < settings.ORCHESTRATOR_MAX_LLM_CALLS
        and state.estimated_tokens_used < settings.ORCHESTRATOR_TOKEN_BUDGET
        and state.execution_iteration == 1
    ):
        evidence_brief = {
            agent_key: {
                "summary": out.get("summary"),
                "limitations": out.get("limitations", []),
                "missing_evidence": out.get("missing_evidence", []),
            }
            for agent_key, out in state.agent_outputs.items()
        }
        sys_prompt = (
            "You are the Evidence Evaluator for GovPath AI. Inspect the executed agents' summaries and decide if "
            "sufficient evidence exists to answer the user's objective, or if additional agents/tools are required.\n"
            "Return ONLY valid JSON: {sufficient_evidence (bool), additional_agents (list[str]), "
            "additional_tools (list[str]), missing_evidence (list[str]), decision_summary (str), stop_reason (str)}.\n"
            f"Valid agents: {', '.join(VALID_AGENTS)}. Already executed: {sorted(executed_agents)}. "
            f"plan_generation_allowed={state.action_constraints.plan_generation_allowed}. "
            "NEVER request StudyOptimizationAgent if plan_generation_allowed is false."
        )
        usr_prompt = (
            f"User objective: {plan.user_objective if plan else state.query}\n"
            f"Query category: {plan.query_category if plan else 'general_counselling'}\n"
            f"Executed evidence summary: {json.dumps(evidence_brief)}"
        )
        llm_eval = generate_structured_json(
            system_prompt=sys_prompt,
            user_prompt=usr_prompt,
            schema_model=FollowUpDecision,
            temperature=0.1,
            max_tokens=400,
        )
        state.llm_calls_used += 1
        state.estimated_tokens_used += llm_eval.tokens_used
        if llm_eval.ok and isinstance(llm_eval.data, FollowUpDecision):
            dec = llm_eval.data
            dec.additional_agents = [
                a for a in dec.additional_agents
                if a in VALID_AGENTS
                and a not in executed_agents
                and not (a == "StudyOptimizationAgent" and not state.action_constraints.plan_generation_allowed)
            ]
            dec.additional_tools = [
                t for t in dec.additional_tools
                if registry.is_allowed(t)
                and not (t == "generate_study_plan_preview" and not state.action_constraints.plan_preview_allowed)
            ]
            if not dec.additional_agents and not dec.additional_tools:
                dec.sufficient_evidence = True
            return dec

    if det_additional_agents:
        return FollowUpDecision(
            sufficient_evidence=False,
            additional_agents=det_additional_agents,
            additional_tools=det_additional_tools,
            missing_evidence=missing,
            decision_summary=f"Follow-up justified based on intermediate evidence: adding {det_additional_agents}.",
            stop_reason="followup_required",
        )

    return FollowUpDecision(
        sufficient_evidence=True,
        missing_evidence=missing,
        decision_summary="Sufficient evidence collected across selected agents.",
        stop_reason="sufficient_evidence",
    )
