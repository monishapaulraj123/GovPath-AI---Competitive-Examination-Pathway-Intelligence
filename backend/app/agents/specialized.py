"""
Six Specialized Tool-Grounded GovPath AI Agents.
Each agent executes approved tools from ToolRegistry backed by the real computational engines
and returns a validated structured output.
"""

from datetime import datetime, timezone
import time
from typing import Any, Optional
import uuid
from sqlalchemy.orm import Session

from app.agents.schemas import AgentOutput, OrchestrationState, ToolExecutionRecord
from app.agents.tool_registry import ToolRegistry, get_tool_registry


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_tool(
    registry: ToolRegistry,
    db: Session,
    user_id: int,
    tool_name: str,
    args: dict[str, Any],
    state: Optional[OrchestrationState],
    agent_name: str,
    cache: Optional[dict[str, dict[str, Any]]],
    tools_used: list[str],
    evidence_refs: list[str],
    limitations: list[str],
) -> Optional[dict[str, Any]]:
    res = registry.execute(
        db=db,
        user_id=user_id,
        tool_name=tool_name,
        raw_args=args,
        state=state,
        agent_name=agent_name,
        existing_cache=cache,
    )
    if res.ok:
        if tool_name not in tools_used:
            tools_used.append(tool_name)
        evidence_refs.extend(res.evidence_references)
        return res.data
    if res.error:
        limitations.append(res.error)
    return None


class StudentAnalysisAgent:
    name = "Student Analysis Agent"
    agent_key = "StudentAnalysisAgent"

    def run(
        self,
        db: Session,
        user_id: int,
        exam_id: Optional[str] = None,
        registry: Optional[ToolRegistry] = None,
        state: Optional[OrchestrationState] = None,
        cache: Optional[dict[str, dict[str, Any]]] = None,
        requested_tools: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        reg = registry or get_tool_registry()
        tools_used: list[str] = []
        evidence_refs: list[str] = []
        limitations: list[str] = []
        missing_evidence: list[str] = []

        profile = _run_tool(reg, db, user_id, "get_aspirant_profile", {}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}
        constraints = _run_tool(reg, db, user_id, "get_preparation_constraints", {}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}
        eff_exam_id = exam_id or profile.get("primary_target_exam") or "UPSC_CSE"

        readiness = _run_tool(reg, db, user_id, "get_student_readiness", {"exam_id": eff_exam_id}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}
        gaps = _run_tool(reg, db, user_id, "get_competency_evidence", {"exam_id": eff_exam_id}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}
        retention = _run_tool(reg, db, user_id, "get_retention_status", {"exam_id": eff_exam_id}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}

        progress = None
        if not requested_tools or "get_preparation_progress" in requested_tools:
            progress = _run_tool(reg, db, user_id, "get_preparation_progress", {}, state, self.name, cache, tools_used, evidence_refs, limitations)

        if readiness.get("assessments_completed", 0) == 0:
            missing_evidence.append("No completed assessments recorded yet; readiness and gap estimates lack empirical quiz evidence.")
        if readiness.get("has_only_demo_data"):
            limitations.append("Current readiness metrics are derived from initial demonstration seed records.")

        overdue_revs = retention.get("overdue_and_due_soon", [])[:5]
        profile_summary = {
            "display_name": profile.get("display_name", "Aspirant"),
            "daily_hours": constraints.get("daily_study_hours", profile.get("daily_study_hours", 4.5)),
            "days_per_week": constraints.get("days_per_week", profile.get("days_per_week", 6)),
            "timeline_months": constraints.get("timeline_months", profile.get("timeline_months", 12)),
            "primary_target_exam": profile.get("primary_target_exam", eff_exam_id),
            "occupation": profile.get("occupation", ""),
            "state": profile.get("state", ""),
        }

        readiness_summary = {
            "exam_id": readiness.get("exam_id", eff_exam_id),
            "readiness_index": readiness.get("readiness_index", 0.0),
            "competency_coverage": readiness.get("competency_coverage", 0.0),
            "accuracy": readiness.get("accuracy", 0.0),
            "retention_index": readiness.get("retention_index", 0.0),
            "consistency": readiness.get("consistency", 0.0),
            "assessments_completed": readiness.get("assessments_completed", 0),
            "has_only_demo_data": readiness.get("has_only_demo_data", False),
            "subject_breakdown": readiness.get("subject_breakdown", []),
        }

        data_payload = {
            "profile_summary": profile_summary,
            "constraints": constraints,
            "readiness": readiness_summary,
            "top_gaps": gaps.get("top_priorities", [])[:5],
            "subject_gaps": gaps.get("subject_gaps", []),
            "overall_weighted_gap": gaps.get("overall_weighted_gap", 0.0),
            "overdue_revisions": overdue_revs,
            "retention": retention,
            "progress": progress,
        }

        structured = AgentOutput(
            agent=self.name,
            agent_key=self.agent_key,
            status="completed",
            tool_used=" + ".join(tools_used),
            tools_used=tools_used,
            summary=(
                f"Readiness for {eff_exam_id}: {readiness_summary['readiness_index']}% "
                f"(Coverage {readiness_summary['competency_coverage']}%, Accuracy {readiness_summary['accuracy']}%), "
                f"weighted gap {data_payload['overall_weighted_gap']}, {len(overdue_revs)} urgent revision(s)."
            ),
            data=data_payload,
            evidence_refs=evidence_refs,
            limitations=limitations,
            missing_evidence=missing_evidence,
        ).model_dump()

        # Preserve top-level keys for backward compatibility
        structured.update(data_payload)
        return structured


class ExamIntelligenceAgent:
    name = "Exam Intelligence Agent"
    agent_key = "ExamIntelligenceAgent"

    def run(
        self,
        db: Session,
        query: str,
        exam_ids: list[str],
        user_id: int = 1,
        registry: Optional[ToolRegistry] = None,
        state: Optional[OrchestrationState] = None,
        cache: Optional[dict[str, dict[str, Any]]] = None,
        requested_tools: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        reg = registry or get_tool_registry()
        tools_used: list[str] = []
        evidence_refs: list[str] = []
        limitations: list[str] = []
        missing_evidence: list[str] = []

        catalogue = _run_tool(reg, db, user_id, "get_exam_catalogue", {}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}
        valid_ids = {e["exam_id"] for e in catalogue.get("exams", [])}

        exam_summaries: list[dict[str, Any]] = []
        syllabus_highlights: dict[str, list[dict[str, Any]]] = {}

        for eid in exam_ids[:3]:
            if eid not in valid_ids:
                missing_evidence.append(f"Exam '{eid}' is not in the verified GovPath examination catalogue.")
                continue
            struct = _run_tool(reg, db, user_id, "get_exam_structure", {"exam_id": eid}, state, self.name, cache, tools_used, evidence_refs, limitations)
            if struct:
                exam_summaries.append({
                    "exam_id": struct["exam_id"],
                    "name": struct["name"],
                    "authority": struct["conducting_authority"],
                    "stages": [s["stage"] for s in (struct.get("stages") or [])],
                    "eligibility": struct["eligibility_summary"],
                    "verification_note": struct["verification_note"],
                    "official_sources": struct["official_sources"],
                    "recommended_daily_hours": struct.get("recommended_daily_hours"),
                })
            if requested_tools and "get_exam_syllabus" in requested_tools:
                syl = _run_tool(reg, db, user_id, "get_exam_syllabus", {"exam_id": eid}, state, self.name, cache, tools_used, evidence_refs, limitations)
                if syl:
                    syllabus_highlights[eid] = syl.get("requirements", [])[:6]
            if requested_tools and "get_official_exam_sources" in requested_tools:
                _run_tool(reg, db, user_id, "get_official_exam_sources", {"exam_id": eid}, state, self.name, cache, tools_used, evidence_refs, limitations)

        target_for_rag = exam_ids[0] if len(exam_ids) == 1 and exam_ids[0] in valid_ids else None
        rag_res = _run_tool(
            reg,
            db,
            user_id,
            "search_exam_documents",
            {"query": query[:450], "exam_id": target_for_rag, "top_k": 4},
            state,
            self.name,
            cache,
            tools_used,
            evidence_refs,
            limitations,
        ) or {}
        docs = rag_res.get("passages", [])
        if not docs:
            missing_evidence.append("No matching RAG passages found in the local syllabus knowledge base.")

        data_payload = {
            "exam_summaries": exam_summaries,
            "retrieved_passages": docs,
            "syllabus_highlights": syllabus_highlights,
            "supported_exam_ids": sorted(valid_ids),
        }

        structured = AgentOutput(
            agent=self.name,
            agent_key=self.agent_key,
            status="completed",
            tool_used=" + ".join(tools_used),
            tools_used=tools_used,
            summary=f"Retrieved {len(exam_summaries)} verified exam framework(s) and {len(docs)} sanitized RAG passage(s).",
            data=data_payload,
            evidence_refs=evidence_refs,
            limitations=limitations,
            missing_evidence=missing_evidence,
        ).model_dump()
        structured.update(data_payload)
        return structured


class PerformanceDiagnosisAgent:
    name = "Performance Diagnosis Agent"
    agent_key = "PerformanceDiagnosisAgent"

    def run(
        self,
        db: Session,
        user_id: int,
        exam_id: Optional[str] = None,
        registry: Optional[ToolRegistry] = None,
        state: Optional[OrchestrationState] = None,
        cache: Optional[dict[str, dict[str, Any]]] = None,
        requested_tools: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        reg = registry or get_tool_registry()
        tools_used: list[str] = []
        evidence_refs: list[str] = []
        limitations: list[str] = []
        missing_evidence: list[str] = []

        diag = _run_tool(reg, db, user_id, "diagnose_assessment_errors", {}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}
        weak = _run_tool(reg, db, user_id, "get_weak_competencies", {"exam_id": exam_id}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}

        has_data = bool(diag.get("has_data"))
        if not has_data:
            missing_evidence.append("No completed assessment attempts exist to diagnose answer-level error patterns.")
        if diag.get("has_only_demo_data"):
            limitations.append("Diagnosis reflects demonstration seed attempts.")

        data_payload = {
            "has_data": has_data,
            "total_attempts": diag.get("total_attempts", 0),
            "total_mistakes": diag.get("total_mistakes", 0),
            "error_breakdown": diag.get("error_category_breakdown", {}),
            "difficulty_performance": diag.get("difficulty_performance", {}),
            "repeated_weak": diag.get("repeated_weak_competencies", [])[:5],
            "top_gap_competencies": weak.get("top_gap_competencies", [])[:5],
            "recommendations": diag.get("recommendations", []),
        }

        structured = AgentOutput(
            agent=self.name,
            agent_key=self.agent_key,
            status="completed",
            tool_used=" + ".join(tools_used),
            tools_used=tools_used,
            summary=(
                f"Analyzed {data_payload['total_mistakes']} mistake(s) across {data_payload['total_attempts']} attempt(s)."
                if has_data else "No completed assessments available for error diagnosis."
            ),
            data=data_payload,
            evidence_refs=evidence_refs,
            limitations=limitations,
            missing_evidence=missing_evidence,
        ).model_dump()
        structured.update(data_payload)
        return structured


class KnowledgeTransferAgent:
    name = "Knowledge Transfer Agent"
    agent_key = "KnowledgeTransferAgent"

    def run(
        self,
        db: Session,
        user_id: int,
        source_exam_id: str,
        target_exam_id: str,
        registry: Optional[ToolRegistry] = None,
        state: Optional[OrchestrationState] = None,
        cache: Optional[dict[str, dict[str, Any]]] = None,
        extra_exam_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        reg = registry or get_tool_registry()
        tools_used: list[str] = []
        evidence_refs: list[str] = []
        limitations: list[str] = []
        missing_evidence: list[str] = []

        transfer = _run_tool(
            reg,
            db,
            user_id,
            "calculate_transferability",
            {"source_exam_id": source_exam_id, "target_exam_id": target_exam_id},
            state,
            self.name,
            cache,
            tools_used,
            evidence_refs,
            limitations,
        ) or {}

        comparison = None
        if extra_exam_ids and len(extra_exam_ids) >= 2:
            comparison = _run_tool(
                reg,
                db,
                user_id,
                "compare_exams",
                {"exam_ids": extra_exam_ids[:4]},
                state,
                self.name,
                cache,
                tools_used,
                evidence_refs,
                limitations,
            )

        if not transfer:
            missing_evidence.append(f"Unable to compute transferability between {source_exam_id} and {target_exam_id}.")

        data_payload = {
            "source_exam_id": transfer.get("source_exam_id", source_exam_id),
            "target_exam_id": transfer.get("target_exam_id", target_exam_id),
            "source_exam": transfer.get("source_exam_name", source_exam_id),
            "target_exam": transfer.get("target_exam_name", target_exam_id),
            "structural_overlap_percent": transfer.get("structural_overlap_percent", 0.0),
            "effective_transfer_index": transfer.get("effective_transfer_index", 0.0),
            "classification_counts": transfer.get("classification_counts", {}),
            "estimated_additional_hours": transfer.get("estimated_additional_hours", 0.0),
            "top_missing_or_reinforce": transfer.get("top_missing_or_reinforce", [])[:5],
            "effort_note": transfer.get("effort_model_note", ""),
            "multi_exam_comparison": comparison,
        }

        structured = AgentOutput(
            agent=self.name,
            agent_key=self.agent_key,
            status="completed" if transfer else "failed",
            tool_used=" + ".join(tools_used),
            tools_used=tools_used,
            summary=(
                f"{data_payload['source_exam']} -> {data_payload['target_exam']}: "
                f"overlap {data_payload['structural_overlap_percent']}%, "
                f"transfer {data_payload['effective_transfer_index']}%, "
                f"~{data_payload['estimated_additional_hours']} bridge hrs."
                if transfer else "Knowledge transfer computation failed."
            ),
            data=data_payload,
            evidence_refs=evidence_refs,
            limitations=limitations,
            missing_evidence=missing_evidence,
        ).model_dump()
        structured.update(data_payload)
        return structured


class PathwayPlanningAgent:
    name = "Pathway Planning Agent"
    agent_key = "PathwayPlanningAgent"

    def run(
        self,
        db: Session,
        user_id: int,
        switch_exam_id: Optional[str] = None,
        hours: Optional[float] = None,
        days_per_week: Optional[int] = None,
        duration_months: Optional[int] = None,
        focus_subject_ids: Optional[list[str]] = None,
        registry: Optional[ToolRegistry] = None,
        state: Optional[OrchestrationState] = None,
        cache: Optional[dict[str, dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        reg = registry or get_tool_registry()
        tools_used: list[str] = []
        evidence_refs: list[str] = []
        limitations: list[str] = []
        missing_evidence: list[str] = []

        pathways = _run_tool(reg, db, user_id, "get_pathway_recommendations", {}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}

        sim = None
        if switch_exam_id or hours is not None or duration_months is not None or days_per_week is not None:
            sim_args: dict[str, Any] = {}
            if switch_exam_id:
                sim_args["target_exam_id"] = switch_exam_id
            if hours is not None:
                sim_args["daily_hours"] = hours
            if days_per_week is not None:
                sim_args["days_per_week"] = days_per_week
            if duration_months is not None:
                sim_args["duration_months"] = duration_months
            if focus_subject_ids:
                sim_args["focus_subject_ids"] = focus_subject_ids

            sim = _run_tool(reg, db, user_id, "simulate_preparation_constraints", sim_args, state, self.name, cache, tools_used, evidence_refs, limitations)

        top_pathways = pathways.get("pathways", [])[:4]
        data_payload = {
            "primary_exam_id": pathways.get("primary_exam_id"),
            "student_constraints": pathways.get("student_constraints", {}),
            "top_pathways": top_pathways,
            "simulation": sim,
        }

        sim_note = ""
        if sim:
            wa = sim.get("workload_assessment", {})
            sim_note = f" Simulation feasibility: {wa.get('feasibility_status')} (ratio {wa.get('capacity_to_need_ratio')})."

        structured = AgentOutput(
            agent=self.name,
            agent_key=self.agent_key,
            status="completed",
            tool_used=" + ".join(tools_used),
            tools_used=tools_used,
            summary=f"Evaluated {len(top_pathways)} pathway(s).{sim_note}",
            data=data_payload,
            evidence_refs=evidence_refs,
            limitations=limitations,
            missing_evidence=missing_evidence,
        ).model_dump()
        structured.update(data_payload)
        return structured


class StudyOptimizationAgent:
    name = "Study Optimization Agent"
    agent_key = "StudyOptimizationAgent"

    def run(
        self,
        db: Session,
        user_id: int,
        exam_id: str,
        daily_hours: Optional[float] = None,
        days_per_week: Optional[int] = None,
        focus_subjects: Optional[list[str]] = None,
        registry: Optional[ToolRegistry] = None,
        state: Optional[OrchestrationState] = None,
        cache: Optional[dict[str, dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        reg = registry or get_tool_registry()
        tools_used: list[str] = []
        evidence_refs: list[str] = []
        limitations: list[str] = []
        missing_evidence: list[str] = []

        existing = _run_tool(reg, db, user_id, "get_existing_study_tasks", {}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}
        plan_args: dict[str, Any] = {"exam_id": exam_id}
        if daily_hours is not None:
            plan_args["daily_hours"] = daily_hours
        if days_per_week is not None:
            plan_args["days_per_week"] = days_per_week
        if focus_subjects:
            plan_args["focus_subjects"] = focus_subjects

        preview_plan = _run_tool(reg, db, user_id, "generate_study_plan_preview", plan_args, state, self.name, cache, tools_used, evidence_refs, limitations) or {}

        data_payload = {
            "preview_plan": preview_plan,
            "existing_plan": existing,
        }

        structured = AgentOutput(
            agent=self.name,
            agent_key=self.agent_key,
            status="completed" if preview_plan else "failed",
            tool_used=" + ".join(tools_used),
            tools_used=tools_used,
            summary=(
                f"Generated {len(preview_plan.get('tasks', []))}-task adaptive preview for "
                f"{preview_plan.get('exam_id', exam_id)} at {preview_plan.get('daily_hours')}h/day."
                if preview_plan else "Failed to generate study plan preview."
            ),
            data=data_payload,
            evidence_refs=evidence_refs,
            limitations=limitations,
            missing_evidence=missing_evidence,
        ).model_dump()
        structured.update(data_payload)
        return structured
