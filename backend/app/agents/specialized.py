"""
Six Specialized Tool-Grounded GovPath AI Agents.
Each agent executes approved tools from ToolRegistry backed by the real computational engines,
enforces WorkflowActionConstraints, and returns a validated structured output.
"""

from typing import Any, Optional
from sqlalchemy.orm import Session

from app.agents.schemas import AgentOutput, OrchestrationState
from app.agents.tool_registry import ToolRegistry, get_tool_registry


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

        retention: dict[str, Any] = {}
        if not requested_tools or "get_retention_status" in requested_tools:
            retention = _run_tool(reg, db, user_id, "get_retention_status", {"exam_id": eff_exam_id}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}

        progress: dict[str, Any] = {}
        if not requested_tools or "get_preparation_progress" in requested_tools:
            progress = _run_tool(reg, db, user_id, "get_preparation_progress", {}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}

        existing_plan_tasks: dict[str, Any] = {}
        if requested_tools and "get_existing_study_tasks" in requested_tools:
            existing_plan_tasks = _run_tool(
                reg, db, user_id, "get_existing_study_tasks", {}, state, self.name, cache, tools_used, evidence_refs, limitations
            ) or {}

        if profile.get("is_default_assumption") or constraints.get("is_default_assumption"):
            limitations.append(
                "No stored student profile record was found; study capacity figures reflect fallback defaults until profile constraints are saved."
            )

        next_assessment = None
        should_recommend_assessment = (
            (requested_tools and "recommend_next_assessment" in requested_tools)
            or readiness.get("assessments_completed", 0) == 0
        )
        if should_recommend_assessment:
            next_assessment = _run_tool(
                reg, db, user_id, "recommend_next_assessment", {"exam_id": eff_exam_id},
                state, self.name, cache, tools_used, evidence_refs, limitations,
            )

        assessments_completed = int(readiness.get("assessments_completed", 0))
        if assessments_completed == 0:
            missing_evidence.append(
                "No completed assessments recorded yet; measured performance evidence is unavailable. "
                "Unassessed competencies indicate missing measurement, not zero knowledge."
            )
        if readiness.get("has_only_demo_data"):
            limitations.append("Current readiness metrics are derived from initial demonstration seed records.")

        overdue_revs = retention.get("overdue_and_due_soon", [])[:5]
        profile_summary = {
            "user_id": profile.get("user_id", user_id),
            "exists": profile.get("exists", False),
            "display_name": profile.get("display_name", "Aspirant"),
            "daily_hours": constraints.get("daily_study_hours", profile.get("daily_study_hours", 4.5)),
            "days_per_week": constraints.get("days_per_week", profile.get("days_per_week", 6)),
            "timeline_months": constraints.get("timeline_months", profile.get("timeline_months", 12)),
            "weekly_hours": constraints.get("weekly_hours", 27.0),
            "total_horizon_hours": constraints.get("total_horizon_hours", 1400.0),
            "primary_target_exam": profile.get("primary_target_exam", eff_exam_id),
            "occupation": profile.get("occupation", ""),
            "state": profile.get("state", ""),
            "constraints_note": constraints.get("constraints_note", ""),
        }

        readiness_summary = {
            "exam_id": readiness.get("exam_id", eff_exam_id),
            "readiness_index": readiness.get("readiness_index", 0.0),
            "competency_coverage": readiness.get("competency_coverage", 0.0),
            "accuracy": readiness.get("accuracy", 0.0),
            "retention_index": readiness.get("retention_index", 0.0),
            "consistency": readiness.get("consistency", 0.0),
            "assessments_completed": assessments_completed,
            "evidence_points": readiness.get("evidence_points", 0),
            "has_only_demo_data": readiness.get("has_only_demo_data", False),
            "subject_breakdown": readiness.get("subject_breakdown", []),
        }

        evidence_classification = {
            "has_verified_assessment_evidence": assessments_completed > 0,
            "assessments_completed": assessments_completed,
            "total_evidence_records": gaps.get("total_evidence_records", 0),
            "assessed_competencies_count": gaps.get("assessed_competencies_count", 0),
            "assessed_competencies": gaps.get("assessed_competencies", []),
            "missing_competencies_count": gaps.get("missing_competencies_count", 0),
            "missing_competencies": gaps.get("missing_competencies", []),
            "stored_activity": {
                "profile_exists": profile.get("exists", False),
                "has_active_study_plan": progress.get("has_active_study_plan", False),
                "active_plan_exam": progress.get("active_plan_exam"),
                "total_tasks": progress.get("total_tasks", 0),
                "completed_tasks": progress.get("completed_tasks", 0),
                "recent_attempts": progress.get("recent_attempts", []),
            },
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
            "existing_plan_tasks": existing_plan_tasks,
            "evidence_classification": evidence_classification,
            "next_assessment_recommendation": next_assessment,
        }

        structured = AgentOutput(
            agent=self.name,
            agent_key=self.agent_key,
            status="completed",
            tool_used=" + ".join(tools_used),
            tools_used=tools_used,
            summary=(
                f"{eff_exam_id}: assessments={assessments_completed}, "
                f"assessed_competencies={evidence_classification['assessed_competencies_count']}, "
                f"unassessed={evidence_classification['missing_competencies_count']}, "
                f"readiness={readiness_summary['readiness_index']}%."
            ),
            data=data_payload,
            evidence_refs=evidence_refs,
            limitations=limitations,
            missing_evidence=missing_evidence,
        ).model_dump()

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
                    "short_name": struct["short_name"],
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

        # Consume shared StudentAnalysisAgent retention trends from orchestration state so an improving
        # competency (with only 1 historical mistake) is not misclassified as weak.
        sa_ret_items = []
        if state is not None:
            sa_ret_items = (
                state.retrieved_evidence.get("StudentAnalysisAgent", {})
                .get("retention", {})
                .get("items", [])
            )
        improving_cids = {
            item["competency_id"]
            for item in sa_ret_items
            if item.get("retention_trend") == "Improving" and float(item.get("current_estimate", 0.0)) >= 70.0
        }
        filtered_repeated_weak = [
            w for w in diag.get("repeated_weak_competencies", [])
            if w.get("is_repeated_pattern") or w.get("competency_id") not in improving_cids
        ][:5]
        filtered_top_gaps = [
            g for g in weak.get("top_gap_competencies", [])
            if g.get("competency_id") not in improving_cids
        ][:5]

        data_payload = {
            "has_data": has_data,
            "total_attempts": diag.get("total_attempts", 0),
            "total_mistakes": diag.get("total_mistakes", 0),
            "error_breakdown": diag.get("error_category_breakdown", {}),
            "difficulty_performance": diag.get("difficulty_performance", {}),
            "repeated_weak": filtered_repeated_weak,
            "excluded_improving_competencies": sorted(improving_cids),
            "top_gap_competencies": filtered_top_gaps,
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
        if extra_exam_ids and len(extra_exam_ids) > 2:
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
        else:
            disclosure = transfer.get("transfer_index_disclosure")
            if disclosure and transfer.get("evidence_basis") != "evidence_backed":
                limitations.append(disclosure)
            if transfer.get("assessments_completed", 0) == 0:
                missing_evidence.append(
                    f"No completed assessment evidence exists for {source_exam_id} or {target_exam_id}; "
                    "shared competencies reflect theoretical syllabus overlap, not verified individual proficiency."
                )

        data_payload = {
            "source_exam_id": transfer.get("source_exam_id", source_exam_id),
            "target_exam_id": transfer.get("target_exam_id", target_exam_id),
            "source_exam": transfer.get("source_exam_name", source_exam_id),
            "target_exam": transfer.get("target_exam_name", target_exam_id),
            "structural_overlap_percent": transfer.get("structural_overlap_percent", 0.0),
            "shared_competency_count": transfer.get("shared_competency_count", 0),
            "target_only_competency_count": transfer.get("target_only_competency_count", 0),
            "effective_transfer_index": transfer.get("effective_transfer_index", 0.0),
            "verified_mastery_transfer_percent": transfer.get("verified_mastery_transfer_percent", 0.0),
            "assessments_completed": transfer.get("assessments_completed", 0),
            "evidence_backed_shared_count": transfer.get("evidence_backed_shared_count", 0),
            "unassessed_shared_count": transfer.get("unassessed_shared_count", 0),
            "evidence_basis": transfer.get("evidence_basis", "structural_baseline_only"),
            "transfer_index_label": transfer.get("transfer_index_label", "Model-Estimated Potential Transfer Index"),
            "transfer_index_disclosure": transfer.get("transfer_index_disclosure", ""),
            "classification_counts": transfer.get("classification_counts", {}),
            "estimated_additional_hours": transfer.get("estimated_additional_hours", 0.0),
            "top_missing_or_reinforce": transfer.get("top_missing_or_reinforce", [])[:6],
            "target_only_competencies_sample": transfer.get("target_only_competencies_sample", [])[:6],
            "assessed_shared_competencies": transfer.get("assessed_shared_competencies", [])[:6],
            "shared_competencies_sample": transfer.get("shared_competencies_sample", [])[:8],
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
                f"structural_overlap={data_payload['structural_overlap_percent']}%, "
                f"model_transfer={data_payload['effective_transfer_index']}% ({data_payload['evidence_basis']}), "
                f"verified_mastery_transfer={data_payload['verified_mastery_transfer_percent']}%."
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
        feasibility_only: bool = False,
        registry: Optional[ToolRegistry] = None,
        state: Optional[OrchestrationState] = None,
        cache: Optional[dict[str, dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        reg = registry or get_tool_registry()
        tools_used: list[str] = []
        evidence_refs: list[str] = []
        limitations: list[str] = []
        missing_evidence: list[str] = []

        pathways: dict[str, Any] = {}
        if not feasibility_only:
            pathways = _run_tool(reg, db, user_id, "get_pathway_recommendations", {}, state, self.name, cache, tools_used, evidence_refs, limitations) or {}

        sim = None
        if feasibility_only or switch_exam_id or hours is not None or duration_months is not None or days_per_week is not None:
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
        feasibility_risks: list[str] = []
        feasibility_assumptions: list[str] = []
        if sim:
            wa = sim.get("workload_assessment", {})
            bc = sim.get("baseline_comparison", {})
            ratio = wa.get("capacity_to_need_ratio", 0.0)
            if wa.get("feasibility_status") == "Time-Constrained":
                feasibility_risks.append(
                    f"Available time ({wa.get('total_available_hours')}h) is below estimated gap-closure workload "
                    f"({wa.get('estimated_required_hours')}h, capacity ratio {ratio})."
                )
            if bc.get("current_readiness_index", 0.0) == 0.0:
                feasibility_risks.append(
                    "Baseline readiness is 0.0% because no assessments are completed; actual required study hours may be lower if prior knowledge exists."
                )
            feasibility_assumptions.append(sim.get("disclaimer", ""))

        data_payload = {
            "primary_exam_id": pathways.get("primary_exam_id") or (sim["scenario"]["target_exam_id"] if sim else None),
            "student_constraints": pathways.get("student_constraints", {}),
            "top_pathways": top_pathways,
            "simulation": sim,
            "feasibility_risks": feasibility_risks,
            "feasibility_assumptions": feasibility_assumptions,
        }

        sim_note = ""
        if sim:
            wa = sim.get("workload_assessment", {})
            sim_note = f" Feasibility={wa.get('feasibility_status')} (ratio={wa.get('capacity_to_need_ratio')})."

        structured = AgentOutput(
            agent=self.name,
            agent_key=self.agent_key,
            status="completed",
            tool_used=" + ".join(tools_used),
            tools_used=tools_used,
            summary=(
                f"Evaluated feasibility for {sim['scenario']['target_exam_id']}.{sim_note}"
                if feasibility_only and sim else f"Evaluated {len(top_pathways)} pathway(s).{sim_note}"
            ),
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

        # Enforce workflow action constraints before executing any study-plan tools
        if state is not None:
            ac = state.action_constraints
            if ac.investigation_only or not ac.plan_generation_allowed or not ac.plan_preview_allowed:
                reason = "Blocked by workflow action constraints: study plan generation/preview is prohibited."
                return AgentOutput(
                    agent=self.name,
                    agent_key=self.agent_key,
                    status="skipped",
                    tool_used="",
                    tools_used=[],
                    summary=reason,
                    data={"preview_plan": {}, "existing_plan": {}, "blocked_reason": reason},
                    limitations=[reason],
                ).model_dump()

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
