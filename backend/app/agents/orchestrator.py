"""
Controlled Agentic AI Orchestrator & 6 Specialized Tool-Grounded Agents.
Follows an explicit multi-step workflow:
1. Intent & workflow routing
2. Retrieve student profile, readiness, gaps, graph, and RAG context
3. Invoke specialized agents with real backend tools
4. Validate grounded numbers & non-fabrication guardrails
5. Synthesize structured explanation (with optional external LLM refinement)
6. Return citations, transparent agent trace, and confirmable action proposals
"""

import re
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.agents.llm_client import generate_llm_response, get_llm_status
from app.engines.diagnosis import compute_performance_diagnosis
from app.engines.gap_analysis import compute_gap_analysis
from app.engines.knowledge_graph import CompetencyGraphEngine
from app.engines.planner import build_adaptive_study_plan, generate_pathway_recommendations
from app.engines.rag import RAGEngine
from app.engines.readiness import compute_readiness_profile
from app.engines.retention import compute_retention_tracker
from app.engines.simulator import run_what_if_simulation
from app.engines.transfer import analyze_knowledge_transfer
from app.models import Exam, StudentProfile

EXAM_KEYWORDS = {
    "UPSC_CSE": ["upsc", "cse", "ias", "ips", "civil services"],
    "TNPSC_GRP1": ["tnpsc group 1", "tnpsc group i", "group 1", "group i", "tnpsc"],
    "TNPSC_GRP2": ["tnpsc group 2", "tnpsc group ii", "group 2", "group ii", "group 2a"],
    "SSC_CGL": ["ssc cgl", "cgl", "ssc"],
    "SSC_CHSL": ["ssc chsl", "chsl"],
    "IBPS_PO": ["ibps", "banking", "bank po", "po"],
    "RRB_NTPC": ["rrb", "railway", "ntpc"],
    "UPSC_CDS": ["cds", "defence", "defense"],
}


def detect_mentioned_exams(query: str, default_primary: str) -> list[str]:
    q = query.lower()
    found: list[str] = []
    # Match specific phrases first
    ordered_keys = [
        "TNPSC_GRP2", "TNPSC_GRP1", "SSC_CHSL", "SSC_CGL", "UPSC_CDS", "UPSC_CSE", "IBPS_PO", "RRB_NTPC"
    ]
    for ex_id in ordered_keys:
        for kw in EXAM_KEYWORDS[ex_id]:
            if re.search(rf"\b{re.escape(kw)}\b", q):
                if ex_id not in found:
                    found.append(ex_id)
                break
    if not found:
        found.append(default_primary)
    return found


class ExamIntelligenceAgent:
    name = "Exam Intelligence Agent"

    def run(self, db: Session, query: str, exam_ids: list[str]) -> dict[str, Any]:
        rag = RAGEngine(db)
        exams = {e.id: e for e in db.query(Exam).all()}
        target_id = exam_ids[0] if exam_ids else None
        docs = rag.retrieve(query, exam_id=target_id if len(exam_ids) == 1 else None, top_k=4)

        exam_summaries = []
        for eid in exam_ids[:3]:
            ex = exams.get(eid)
            if ex:
                exam_summaries.append({
                    "exam_id": ex.id,
                    "name": ex.name,
                    "authority": ex.conducting_authority,
                    "stages": [s["stage"] for s in (ex.stages or [])],
                    "eligibility": ex.eligibility_summary,
                    "verification_note": ex.verification_note,
                    "official_sources": ex.official_sources,
                })
        return {
            "agent": self.name,
            "tool_used": "RAGEngine.retrieve + ExamCatalog",
            "exam_summaries": exam_summaries,
            "retrieved_passages": docs,
        }


class StudentAnalysisAgent:
    name = "Student Analysis Agent"

    def run(self, db: Session, user_id: int, exam_id: str) -> dict[str, Any]:
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
        readiness = compute_readiness_profile(db, user_id, exam_id)
        gaps = compute_gap_analysis(db, user_id, exam_id)
        retention = compute_retention_tracker(db, user_id, exam_id)
        return {
            "agent": self.name,
            "tool_used": "ReadinessModel + GapEngine + RetentionTracker",
            "profile_summary": {
                "display_name": profile.display_name if profile else "Aspirant",
                "daily_hours": profile.daily_study_hours if profile else 4.5,
                "days_per_week": profile.days_per_week if profile else 6,
                "timeline_months": profile.timeline_months if profile else 12,
                "primary_target_exam": profile.primary_target_exam if profile else exam_id,
                "occupation": profile.current_occupation if profile else "",
            },
            "readiness": {
                "readiness_index": readiness["readiness_index"],
                "competency_coverage": readiness["competency_coverage"],
                "accuracy": readiness["accuracy"],
                "retention_index": readiness["retention_index"],
                "consistency": readiness["consistency"],
                "assessments_completed": readiness["assessments_completed"],
                "has_only_demo_data": readiness["has_only_demo_data"],
            },
            "top_gaps": gaps["top_priorities"][:5],
            "overall_weighted_gap": gaps["overall_weighted_gap"],
            "overdue_revisions": [
                r for r in retention["items"] if r["revision_status"] in ("Revision Overdue", "Due Soon")
            ][:5],
        }


class PerformanceDiagnosisAgent:
    name = "Performance Diagnosis Agent"

    def run(self, db: Session, user_id: int) -> dict[str, Any]:
        diag = compute_performance_diagnosis(db, user_id)
        return {
            "agent": self.name,
            "tool_used": "PerformanceDiagnosisEngine",
            "has_data": diag["has_data"],
            "total_mistakes": diag.get("total_mistakes", 0),
            "error_breakdown": diag.get("error_category_breakdown", {}),
            "repeated_weak": diag.get("repeated_weak_competencies", [])[:4],
            "recommendations": diag.get("recommendations", []),
        }


class KnowledgeTransferAgent:
    name = "Knowledge Transfer Agent"

    def run(self, db: Session, user_id: int, source_exam_id: str, target_exam_id: str) -> dict[str, Any]:
        transfer = analyze_knowledge_transfer(db, user_id, source_exam_id, target_exam_id)
        graph = CompetencyGraphEngine(db)
        overlap = graph.query_shared_competencies(source_exam_id, target_exam_id)
        return {
            "agent": self.name,
            "tool_used": "CompetencyGraphEngine + KnowledgeTransferEngine",
            "source_exam": transfer["source_exam_name"],
            "target_exam": transfer["target_exam_name"],
            "structural_overlap_percent": overlap["structural_overlap_percent"],
            "effective_transfer_index": transfer["effective_transfer_index"],
            "classification_counts": transfer["classification_counts"],
            "estimated_additional_hours": transfer["estimated_additional_hours"],
            "top_missing_or_reinforce": [
                c for c in transfer["competencies"]
                if c["classification"] in ("Not Covered", "Requires Reinforcement")
            ][:5],
            "effort_note": transfer["effort_model_note"],
        }


class PathwayPlanningAgent:
    name = "Pathway Planning Agent"

    def run(self, db: Session, user_id: int, switch_exam_id: Optional[str] = None, hours: Optional[float] = None) -> dict[str, Any]:
        pathways = generate_pathway_recommendations(db, user_id)
        sim = None
        if switch_exam_id or hours is not None:
            profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
            sim = run_what_if_simulation(
                db,
                user_id,
                target_exam_id=switch_exam_id or (profile.primary_target_exam if profile else "UPSC_CSE"),
                daily_hours=hours or (profile.daily_study_hours if profile else 4.5),
                days_per_week=profile.days_per_week if profile else 6,
                duration_months=profile.timeline_months if profile else 12,
            )
        return {
            "agent": self.name,
            "tool_used": "PathwayRecommendationEngine + WhatIfSimulator",
            "top_pathways": pathways["pathways"][:4],
            "simulation": sim,
        }


class StudyOptimizationAgent:
    name = "Study Optimization Agent"

    def run(self, db: Session, user_id: int, exam_id: str, daily_hours: Optional[float] = None) -> dict[str, Any]:
        preview_plan = build_adaptive_study_plan(
            db, user_id, exam_id=exam_id, daily_hours=daily_hours, persist=False
        )
        return {
            "agent": self.name,
            "tool_used": "AdaptiveStudyPlanner(preview)",
            "preview_plan": preview_plan,
        }


class AgentOrchestrator:
    """Routes user requests to specialized agents, validates grounded data, and builds structured replies."""

    def handle_query(self, db: Session, user_id: int, message: str) -> dict[str, Any]:
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
        primary_exam = profile.primary_target_exam if profile else "UPSC_CSE"
        q_lower = message.lower()

        mentioned_exams = detect_mentioned_exams(message, primary_exam)
        hours_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)", q_lower)
        requested_hours = float(hours_match.group(1)) if hours_match else None
        if requested_hours is not None:
            requested_hours = max(0.5, min(14.0, requested_hours))

        # 1. Determine workflow intents
        wants_transfer = any(k in q_lower for k in ["transfer", "overlap", "switch", "move from", "between"]) or len(mentioned_exams) >= 2
        wants_compare = any(k in q_lower for k in ["compare", "difference", "vs", "versus"])
        wants_diagnosis = any(k in q_lower for k in ["losing marks", "mistake", "error", "wrong", "why am i", "diagnosis", "accuracy"])
        wants_revision = any(k in q_lower for k in ["revise", "revision", "retention", "forget", "today"])
        wants_plan = any(k in q_lower for k in ["study plan", "schedule", "adjust", "hours per day", "hrs per day", "time table", "timetable"])
        wants_pathway = any(k in q_lower for k in ["which exam", "which government", "pathway", "consider", "begin", "start", "backup", "career"])
        wants_dates_or_vacancies = any(k in q_lower for k in ["exam date", "notification date", "last date", "vacancy", "vacancies", "cutoff 202"])

        agent_trace: list[dict[str, Any]] = []
        outputs: dict[str, Any] = {}

        # Always ground in Student Analysis + Exam Intelligence
        sa_out = StudentAnalysisAgent().run(db, user_id, mentioned_exams[0])
        outputs["student_analysis"] = sa_out
        agent_trace.append({"agent": sa_out["agent"], "tool": sa_out["tool_used"], "status": "completed"})

        ei_out = ExamIntelligenceAgent().run(db, message, mentioned_exams)
        outputs["exam_intelligence"] = ei_out
        agent_trace.append({"agent": ei_out["agent"], "tool": ei_out["tool_used"], "status": "completed"})

        if wants_transfer or wants_compare:
            src = mentioned_exams[0] if len(mentioned_exams) >= 2 else primary_exam
            tgt = mentioned_exams[1] if len(mentioned_exams) >= 2 else (
                "TNPSC_GRP1" if src != "TNPSC_GRP1" else "SSC_CGL"
            )
            kt_out = KnowledgeTransferAgent().run(db, user_id, src, tgt)
            outputs["knowledge_transfer"] = kt_out
            agent_trace.append({"agent": kt_out["agent"], "tool": kt_out["tool_used"], "status": "completed"})

        if wants_diagnosis:
            pd_out = PerformanceDiagnosisAgent().run(db, user_id)
            outputs["performance_diagnosis"] = pd_out
            agent_trace.append({"agent": pd_out["agent"], "tool": pd_out["tool_used"], "status": "completed"})

        if wants_pathway or requested_hours is not None or "switch" in q_lower:
            pp_out = PathwayPlanningAgent().run(
                db, user_id,
                switch_exam_id=mentioned_exams[-1] if "switch" in q_lower else None,
                hours=requested_hours,
            )
            outputs["pathway_planning"] = pp_out
            agent_trace.append({"agent": pp_out["agent"], "tool": pp_out["tool_used"], "status": "completed"})

        if wants_plan or requested_hours is not None:
            so_out = StudyOptimizationAgent().run(db, user_id, mentioned_exams[0], daily_hours=requested_hours)
            outputs["study_optimization"] = so_out
            agent_trace.append({"agent": so_out["agent"], "tool": so_out["tool_used"], "status": "completed"})

        # Build citations from RAG passages & official sources
        citations: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for p in ei_out.get("retrieved_passages", []):
            if p["title"] not in seen_titles:
                seen_titles.add(p["title"])
                citations.append({
                    "title": p["title"],
                    "source_name": p["source_name"],
                    "source_url": p["source_url"],
                    "verified_status": p["verified_status"],
                    "snippet": p["content"][:220] + ("..." if len(p["content"]) > 220 else ""),
                })

        # Safe state-change proposal (requires explicit user confirmation in UI)
        proposed_action = None
        if wants_plan or requested_hours is not None:
            target_for_plan = mentioned_exams[0]
            eff_hrs = requested_hours or (profile.daily_study_hours if profile else 4.5)
            proposed_action = {
                "proposal_type": "apply_study_plan",
                "label": f"Generate & Activate {target_for_plan} Study Plan ({eff_hrs}h/day)",
                "description": "Applies the optimized weekly study schedule based on your current gaps and retention queue.",
                "payload": {"exam_id": target_for_plan, "daily_hours": eff_hrs},
            }

        # Construct grounded deterministic reply first (never fabricated)
        grounded_reply = self._compose_grounded_reply(
            message=message,
            outputs=outputs,
            wants_dates_or_vacancies=wants_dates_or_vacancies,
            wants_transfer=wants_transfer,
            wants_compare=wants_compare,
            wants_diagnosis=wants_diagnosis,
            wants_revision=wants_revision,
            wants_plan=wants_plan,
            wants_pathway=wants_pathway,
            requested_hours=requested_hours,
        )

        # Optional LLM polish strictly constrained to grounded facts
        llm_status = get_llm_status()
        final_reply = grounded_reply
        if llm_status["configured"]:
            system_prompt = (
                "You are GovPath AI Counsellor. Rewrite and refine the grounded analysis below into clear, "
                "concise, encouraging academic guidance. STRICT RULES: Do NOT invent any scores, percentages, "
                "dates, vacancies, or exam rules not present in the grounded facts. Preserve all disclaimers."
            )
            user_prompt = f"User Question: {message}\n\nGrounded Backend Analysis:\n{grounded_reply}"
            polished = generate_llm_response(system_prompt, user_prompt)
            if polished:
                final_reply = polished

        return {
            "reply": final_reply,
            "citations": citations,
            "agent_trace": agent_trace,
            "proposed_action": proposed_action,
            "llm_mode": llm_status,
        }

    def _compose_grounded_reply(
        self,
        message: str,
        outputs: dict[str, Any],
        wants_dates_or_vacancies: bool,
        wants_transfer: bool,
        wants_compare: bool,
        wants_diagnosis: bool,
        wants_revision: bool,
        wants_plan: bool,
        wants_pathway: bool,
        requested_hours: Optional[float],
    ) -> str:
        sa = outputs["student_analysis"]
        ei = outputs["exam_intelligence"]
        r = sa["readiness"]
        prof = sa["profile_summary"]
        lines: list[str] = []

        if wants_dates_or_vacancies:
            lines.append(
                "**Verification Notice:** GovPath AI does not fabricate or assume live examination dates, "
                "vacancy counts, or cycle-specific notification cutoffs. Please verify active cycle dates directly "
                "from the official portals listed in the citations below."
            )
            lines.append("")

        demo_tag = " *(based on initial demonstration records)*" if r.get("has_only_demo_data") else ""
        lines.append(
            f"### Personalized Context for {prof['display_name']}\n"
            f"- **Primary Target:** {prof['primary_target_exam']} | **Availability:** {prof['daily_hours']}h/day × {prof['days_per_week']} days/week\n"
            f"- **Measured Readiness Alignment{demo_tag}:** **{r['readiness_index']}%** "
            f"(Coverage: {r['competency_coverage']}%, Accuracy: {r['accuracy']}%, Retention: {r['retention_index']}%)\n"
            f"- *Note: Readiness reflects measured competency alignment against the exam model, not an official pass probability.*"
        )

        if "knowledge_transfer" in outputs and (wants_transfer or wants_compare):
            kt = outputs["knowledge_transfer"]
            cc = kt["classification_counts"]
            lines.append(
                f"\n### Knowledge Transfer & Comparison ({kt['source_exam']} → {kt['target_exam']})\n"
                f"- **Structural Graph Overlap:** **{kt['structural_overlap_percent']}%** of target competencies\n"
                f"- **Effective Student Transfer Index:** **{kt['effective_transfer_index']}%**\n"
                f"- **Breakdown:** {cc['Fully Transferable']} Fully Transferable, "
                f"{cc['Partially Transferable']} Partially Transferable, "
                f"{cc['Requires Reinforcement']} Require Reinforcement, "
                f"{cc['Not Covered']} New/Not Covered\n"
                f"- **Model-Estimated Additional Effort:** ~**{kt['estimated_additional_hours']} hours** *(approximation based on remaining depth gaps)*"
            )
            if kt["top_missing_or_reinforce"]:
                top_items = ", ".join(f"{c['competency_name']} ({c['classification']})" for c in kt["top_missing_or_reinforce"][:3])
                lines.append(f"- **Key Bridge Priorities:** {top_items}")

        if "performance_diagnosis" in outputs and wants_diagnosis:
            pd_out = outputs["performance_diagnosis"]
            if not pd_out["has_data"]:
                lines.append("\n### Performance Diagnosis\nNo completed assessment attempts found yet. Take a diagnostic or topic quiz first so I can diagnose error patterns from evidence.")
            else:
                err_str = ", ".join(f"{k}: {v}" for k, v in pd_out["error_breakdown"].items()) or "No errors recorded"
                lines.append(
                    f"\n### Performance & Error Diagnosis\n"
                    f"- **Recorded Mistakes Analyzed:** {pd_out['total_mistakes']} ({err_str})"
                )
                for rec in pd_out["recommendations"][:3]:
                    lines.append(f"- {rec}")

        if wants_revision or "revision" in message.lower():
            revs = sa.get("overdue_revisions", [])
            if revs:
                rev_list = "\n".join(
                    f"  - **{rv['topic_name']}** ({rv['subject_name']}) — *{rv['revision_status']}* (Last score: {rv['current_estimate']}%)"
                    for rv in revs[:4]
                )
                lines.append(f"\n### Recommended Revision Queue Today\n{rev_list}")
            else:
                lines.append("\n### Revision Queue\nAll assessed competencies are currently within their target review window. Focus on expanding unassessed topics.")

        if sa["top_gaps"]:
            gap_list = "\n".join(
                f"  - **{g['topic_name']}** ({g['subject_name']}): Required {g['required_level']} vs Current {g['current_evidence']} → **Gap {g['gap']} ({g['priority']})**"
                for g in sa["top_gaps"][:4]
            )
            lines.append(f"\n### Priority Competency Gaps\n{gap_list}")

        if "pathway_planning" in outputs and (wants_pathway or requested_hours is not None):
            pp = outputs["pathway_planning"]
            p_lines = "\n".join(
                f"  - **{p['short_name']}** ({p['role']}) — Suitability: **{p['suitability_score']}/100**, Readiness: {p['readiness_index']}%, Transfer: {p['transfer_from_primary_percent']}%"
                for p in pp["top_pathways"][:3]
            )
            lines.append(f"\n### Recommended Exam Pathways\n{p_lines}")
            if pp.get("simulation"):
                bc = pp["simulation"]["baseline_comparison"]
                wa = pp["simulation"]["workload_assessment"]
                lines.append(
                    f"\n### Scenario Impact ({pp['simulation']['scenario']['daily_hours']}h/day)\n"
                    f"- **Projected Readiness Shift:** {bc['current_readiness_index']}% → **{bc['projected_readiness_index']}%** "
                    f"(+{bc['readiness_delta']} pts) | **Feasibility:** {wa['feasibility_status']}"
                )

        if "study_optimization" in outputs and (wants_plan or requested_hours is not None):
            sp = outputs["study_optimization"]["preview_plan"]
            sample_tasks = "\n".join(
                f"  - Day {t['day_index']}: **{t['title']}** ({t['duration_minutes']} mins)"
                for t in sp["tasks"][:4]
            )
            lines.append(
                f"\n### Proposed Adaptive Study Plan ({sp['daily_hours']}h/day)\n"
                f"{sp['generation_rationale']}\n{sample_tasks}\n"
                f"*(Use the confirmation button below to activate this plan without losing control of your existing schedule.)*"
            )

        if ei.get("exam_summaries") and not (wants_transfer or wants_diagnosis or wants_plan):
            ex0 = ei["exam_summaries"][0]
            lines.append(
                f"\n### Verified Exam Reference: {ex0['name']}\n"
                f"- **Conducting Authority:** {ex0['authority']}\n"
                f"- **Stages:** {' → '.join(ex0['stages'])}\n"
                f"- **Eligibility Summary:** {ex0['eligibility']}"
            )

        return "\n".join(lines)
