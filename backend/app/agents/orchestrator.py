"""
Phase 1 Upgraded Agentic AI Orchestrator.
Implements prohibition-aware structured planning, dynamic agent/tool selection,
bounded iterative execution, shared validated state, honest evidence grounding, and transparent trace.
"""

from datetime import datetime, timezone
import logging
import re
import time
from typing import Any, Optional
import uuid
from sqlalchemy.orm import Session

from app.agents.llm_client import generate_llm_response_detailed, get_llm_status
from app.agents.planner import (
    EXAM_ALIASES,
    evaluate_evidence_and_plan_followup,
    plan_user_query,
)
from app.agents.schemas import (
    AgentName,
    OrchestrationState,
    StructuredPlan,
    ToolExecutionRecord,
)
from app.agents.specialized import (
    ExamIntelligenceAgent,
    KnowledgeTransferAgent,
    PathwayPlanningAgent,
    PerformanceDiagnosisAgent,
    StudentAnalysisAgent,
    StudyOptimizationAgent,
)
from app.agents.tool_registry import ToolRegistry, get_tool_registry, sanitize_untrusted_text, sanitize_user_query
from app.config import get_settings
from app.models import StudentProfile

logger = logging.getLogger("govpath.orchestrator")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_mentioned_exams(query: str, default_primary: str) -> list[str]:
    """Backward-compatible helper for detecting exam IDs mentioned in text."""
    q = query.lower()
    found: list[str] = []
    for ex_id, aliases in EXAM_ALIASES.items():
        for kw in aliases:
            if re.search(rf"\b{re.escape(kw)}\b", q):
                if ex_id not in found:
                    found.append(ex_id)
                break
    if not found:
        found.append(default_primary)
    return found


def _verify_numeric_grounding(llm_text: str, grounded_text: str) -> bool:
    """
    Guardrail against LLM hallucinating new percentage values not present in the grounded backend output.
    """
    grounded_pcts = set(re.findall(r"\b\d+(?:\.\d+)?%", grounded_text))
    llm_pcts = set(re.findall(r"\b\d+(?:\.\d+)?%", llm_text))
    ungrounded = llm_pcts - grounded_pcts
    if ungrounded:
        logger.warning("Numeric grounding guardrail rejected LLM polish due to ungrounded percentages: %s", ungrounded)
        return False
    return True


class AgentOrchestrator:
    """
    Bounded, constraint-enforcing, tool-grounded multi-agent orchestrator.
    """

    def __init__(self, registry: Optional[ToolRegistry] = None) -> None:
        self.registry = registry or get_tool_registry()

    def handle_query(
        self,
        db: Session,
        user_id: int,
        message: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        orch_start = time.perf_counter()
        clean_query = sanitize_user_query(message)
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
        primary_exam = profile.primary_target_exam if profile else "UPSC_CSE"

        state = OrchestrationState(
            user_id=user_id,
            query=clean_query,
            conversation_context=conversation_history or [],
            workflow_status="planning",
        )

        # 1. Structured Intent, Constraints & Workflow Planning
        plan = plan_user_query(
            db=db,
            user_id=user_id,
            query=clean_query,
            registry=self.registry,
            state=state,
            conversation_context=conversation_history,
        )
        state.structured_intent = plan
        state.action_constraints = plan.action_constraints
        state.execution_plan = list(plan.execution_sequence)
        state.selected_examination_ids = list(plan.mentioned_examinations)
        state.selected_agents = list(plan.required_agents)
        state.selection_rationale = dict(plan.selection_rationale)
        state.missing_evidence.extend(plan.missing_information)

        # 2. Bounded Iterative Agent & Tool Execution
        state.workflow_status = "executing"
        tool_cache: dict[str, dict[str, Any]] = {}
        agents_to_run: list[AgentName] = list(plan.required_agents)

        while agents_to_run and state.execution_iteration < settings.ORCHESTRATOR_MAX_ITERATIONS:
            elapsed = time.perf_counter() - orch_start
            if elapsed >= settings.ORCHESTRATOR_TIMEOUT_SECONDS:
                state.limitations.append(
                    f"Orchestration timeout reached ({settings.ORCHESTRATOR_TIMEOUT_SECONDS}s); returning partial grounded results."
                )
                break

            state.execution_iteration += 1
            next_batch: list[AgentName] = []

            for agent_key in agents_to_run:
                if time.perf_counter() - orch_start >= settings.ORCHESTRATOR_TIMEOUT_SECONDS:
                    self._append_skip_record(state, agent_key, "orchestrator_timeout_guard", "Orchestration timeout budget reached")
                    continue

                if agent_key == "StudyOptimizationAgent" and (
                    state.action_constraints.investigation_only
                    or not state.action_constraints.plan_generation_allowed
                    or not state.action_constraints.plan_preview_allowed
                ):
                    self._append_skip_record(
                        state,
                        agent_key,
                        "action_constraint_guard",
                        "Study plan generation/preview is prohibited by workflow action constraints.",
                    )
                    continue

                if agent_key == "PerformanceDiagnosisAgent" and "StudentAnalysisAgent" in state.agent_outputs:
                    sa_ready = state.agent_outputs["StudentAnalysisAgent"].get("readiness", {})
                    if int(sa_ready.get("assessments_completed", 0)) == 0:
                        skip_msg = (
                            "Prerequisite unsatisfied: 0 completed assessments recorded; answer-level error diagnosis "
                            "cannot run without completed attempts."
                        )
                        self._append_skip_record(state, agent_key, "prerequisite_guard", skip_msg)
                        if skip_msg not in state.limitations:
                            state.limitations.append(skip_msg)
                        continue

                if agent_key in ("KnowledgeTransferAgent", "StudyOptimizationAgent") and "ExamIntelligenceAgent" in state.agent_outputs:
                    ei_out = state.agent_outputs["ExamIntelligenceAgent"]
                    supported = set(ei_out.get("supported_exam_ids", []))
                    if plan.primary_examination and supported and plan.primary_examination not in supported:
                        skip_msg = (
                            f"Prerequisite unsatisfied: examination '{plan.primary_examination}' is unavailable "
                            f"in the verified exam catalogue."
                        )
                        self._append_skip_record(state, agent_key, "prerequisite_guard", skip_msg)
                        if skip_msg not in state.limitations:
                            state.limitations.append(skip_msg)
                        continue

                if agent_key in state.agent_outputs:
                    self._append_skip_record(
                        state,
                        agent_key,
                        "duplicate_agent_guard",
                        f"{agent_key} already executed in an earlier iteration",
                    )
                    continue

                if state.tool_calls_used >= settings.ORCHESTRATOR_MAX_TOOL_CALLS:
                    self._append_skip_record(
                        state,
                        agent_key,
                        "tool_budget_guard",
                        f"Tool call budget exhausted ({settings.ORCHESTRATOR_MAX_TOOL_CALLS})",
                    )
                    continue

                self._execute_single_agent(
                    db=db,
                    user_id=user_id,
                    agent_key=agent_key,
                    plan=plan,
                    primary_exam=primary_exam,
                    state=state,
                    cache=tool_cache,
                )

            # 3. Evidence Evaluation & Follow-up Decision
            state.workflow_status = "evaluating"
            eval_start = time.perf_counter()
            eval_iso = _utc_iso()
            decision = evaluate_evidence_and_plan_followup(state, self.registry)
            state.missing_evidence.extend(
                m for m in decision.missing_evidence if m not in state.missing_evidence
            )

            state.tool_execution_records.append(
                ToolExecutionRecord(
                    execution_id=f"eval_{uuid.uuid4().hex[:8]}",
                    step_order=len(state.tool_execution_records) + 1,
                    kind="evaluator",
                    agent="Evidence Evaluator",
                    tool=f"iteration_{state.execution_iteration}_check",
                    status="completed",
                    input_summary=f"Executed agents: {list(state.agent_outputs.keys())}",
                    output_summary=f"sufficient={decision.sufficient_evidence}, stop_reason={decision.stop_reason}",
                    started_at=eval_iso,
                    ended_at=_utc_iso(),
                    duration_ms=round((time.perf_counter() - eval_start) * 1000.0, 2),
                )
            )

            if decision.sufficient_evidence or not decision.additional_agents:
                break

            for extra_ag in decision.additional_agents:
                if extra_ag == "StudyOptimizationAgent" and not state.action_constraints.plan_generation_allowed:
                    continue
                if extra_ag not in state.agent_outputs and extra_ag not in next_batch:
                    next_batch.append(extra_ag)
                    if extra_ag not in state.selected_agents:
                        state.selected_agents.append(extra_ag)
                        state.selection_rationale[extra_ag] = "Added by evidence evaluator based on intermediate findings."
            agents_to_run = next_batch

        # 4. Collect Citations from Exam Intelligence RAG Passages
        citations: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        ei_out = state.agent_outputs.get("ExamIntelligenceAgent", {})
        for p in ei_out.get("retrieved_passages", []):
            title = p.get("title", "Reference")
            if title not in seen_titles:
                seen_titles.add(title)
                snippet_src = sanitize_untrusted_text(p.get("content", ""), max_len=240)
                citations.append({
                    "title": title,
                    "source_name": p.get("source_name", "GovPath Knowledge Base"),
                    "source_url": p.get("source_url", ""),
                    "verified_status": p.get("verified_status", "Verified Reference"),
                    "snippet": snippet_src[:220] + ("..." if len(snippet_src) > 220 else ""),
                })
        state.source_references = citations

        # 5. Validated Confirmable Action Proposal (ONLY when permitted by WorkflowActionConstraints)
        proposed_action = self._build_validated_proposal(db, user_id, plan, primary_exam, profile, state, tool_cache)
        state.proposed_action = proposed_action

        # 6. Grounded Response Synthesis
        grounded_reply = self._compose_grounded_reply(state)
        final_reply = grounded_reply

        llm_status = get_llm_status()
        synth_start = time.perf_counter()
        synth_iso = _utc_iso()
        synthesis_mode = "deterministic_grounded"
        synthesis_provider = "grounded_deterministic"
        synthesis_model = "GovPath Grounded Synthesis Engine"
        can_polish_with_llm = (
            llm_status["configured"]
            and not state.fallback_used
            and state.llm_calls_used < settings.ORCHESTRATOR_MAX_LLM_CALLS
            and state.estimated_tokens_used < settings.ORCHESTRATOR_TOKEN_BUDGET
        )
        if can_polish_with_llm:
            prohib_line = (
                f"Prohibited actions (NEVER suggest, preview, or offer): {', '.join(state.action_constraints.explicit_user_prohibitions)}"
                if state.action_constraints.explicit_user_prohibitions
                else "No study plan preview/activation unless explicitly present in Grounded Backend Analysis."
            )
            system_prompt = (
                "You are GovPath AI Counsellor. Rewrite the grounded backend analysis into clear, structured, "
                "honest academic guidance.\n"
                "STRICT GROUNDING RULES:\n"
                "1. Use ONLY numbers, percentages, hours, exam names, and facts present in the Grounded Backend Analysis.\n"
                "2. Do NOT invent any readiness scores, competency scores, assessment records, exam dates, vacancies, cutoffs, or tasks.\n"
                "3. Never claim zero completed assessments means the student has zero real-world knowledge.\n"
                "4. Preserve all limitations, missing-evidence notices, transfer index disclosures, and verification disclaimers.\n"
                f"5. {prohib_line}\n"
                "6. Preserve clear section headings (such as 'Knowledge Transfer' when present)."
            )
            user_prompt = f"User Question: {clean_query}\n\nGrounded Backend Analysis:\n{grounded_reply}"
            llm_res = generate_llm_response_detailed(system_prompt, user_prompt, temperature=0.2, max_tokens=1600)
            state.llm_calls_used += 1
            state.estimated_tokens_used += llm_res.tokens_used

            if llm_res.ok and llm_res.raw_text and _verify_numeric_grounding(llm_res.raw_text, grounded_reply):
                final_reply = llm_res.raw_text
                synthesis_mode = "llm_grounded"
                synthesis_provider = llm_res.provider
                synthesis_model = llm_res.model
                state.tool_execution_records.append(
                    ToolExecutionRecord(
                        execution_id=f"synth_{uuid.uuid4().hex[:8]}",
                        step_order=len(state.tool_execution_records) + 1,
                        kind="synthesizer",
                        agent="Grounded Response Synthesizer",
                        tool=f"llm_grounded_polish({llm_res.provider}:{llm_res.model})",
                        status="completed",
                        output_summary=f"Refined grounded response via {llm_res.provider} ({llm_res.model}) with numeric guardrail passed.",
                        started_at=synth_iso,
                        ended_at=_utc_iso(),
                        duration_ms=llm_res.latency_ms,
                    )
                )
            else:
                reason = llm_res.error or "Numeric grounding guardrail reverted to deterministic grounded response"
                if not llm_res.ok:
                    state.fallback_used = True
                    state.llm_error = state.llm_error or reason
                    state.tool_execution_records.append(
                        ToolExecutionRecord(
                            execution_id=f"synth_err_{uuid.uuid4().hex[:8]}",
                            step_order=len(state.tool_execution_records) + 1,
                            kind="synthesizer",
                            agent="Grounded Response Synthesizer",
                            tool=f"llm_grounded_polish({llm_res.provider}:{llm_res.model})",
                            status="failed",
                            started_at=synth_iso,
                            ended_at=_utc_iso(),
                            duration_ms=llm_res.latency_ms,
                            error_details=reason,
                        )
                    )
                state.limitations.append(f"LLM response synthesis fallback: {reason}")
                state.tool_execution_records.append(
                    ToolExecutionRecord(
                        execution_id=f"synth_{uuid.uuid4().hex[:8]}",
                        step_order=len(state.tool_execution_records) + 1,
                        kind="synthesizer",
                        agent="Grounded Response Synthesizer",
                        tool="deterministic_grounded_synthesizer",
                        status="completed",
                        output_summary=f"Used deterministic grounded reply ({reason}).",
                        started_at=_utc_iso(),
                        ended_at=_utc_iso(),
                        duration_ms=round((time.perf_counter() - synth_start) * 1000.0, 2),
                    )
                )
        else:
            synth_reason = (
                "Used deterministic grounded synthesizer (LLM fallback active)."
                if state.fallback_used
                else "Synthesized response directly from validated backend tool outputs."
            )
            state.tool_execution_records.append(
                ToolExecutionRecord(
                    execution_id=f"synth_{uuid.uuid4().hex[:8]}",
                    step_order=len(state.tool_execution_records) + 1,
                    kind="synthesizer",
                    agent="Grounded Response Synthesizer",
                    tool="deterministic_grounded_synthesizer",
                    status="completed",
                    output_summary=synth_reason,
                    started_at=synth_iso,
                    ended_at=_utc_iso(),
                    duration_ms=round((time.perf_counter() - synth_start) * 1000.0, 2),
                )
            )

        state.final_response = final_reply
        if state.errors or state.limitations or state.missing_evidence:
            state.workflow_status = "clarification_needed" if plan.clarification_required else "completed_with_limitations"
        else:
            state.workflow_status = "completed"

        summary_payload = {
            "workflow_status": state.workflow_status,
            "llm_provider": llm_status["provider"],
            "llm_model": llm_status["model"],
            "planner_mode": plan.planner_mode,
            "planner_provider": plan.planner_provider,
            "synthesis_mode": synthesis_mode,
            "synthesis_provider": synthesis_provider,
            "synthesis_model": synthesis_model,
            "fallback_used": state.fallback_used,
            "llm_error": state.llm_error,
            "query_category": plan.query_category,
            "secondary_categories": plan.secondary_categories,
            "selected_examinations": state.selected_examination_ids,
            "selected_agents": state.selected_agents,
            "selection_rationale": state.selection_rationale,
            "action_constraints": state.action_constraints.model_dump(),
            "iterations": state.execution_iteration,
            "tool_calls_used": state.tool_calls_used,
            "llm_calls_used": state.llm_calls_used,
            "evidence_sources": [
                ref
                for out in state.agent_outputs.values()
                for ref in out.get("evidence_refs", [])
            ],
            "missing_evidence": state.missing_evidence,
            "limitations": state.limitations,
            "clarification_required": plan.clarification_required,
            "clarification_question": plan.clarification_question,
        }

        # Embed summary metadata on synthesizer trace entry so persisted ChatMessage.agent_trace
        # carries full workflow/constraint/fallback transparency on session reload too.
        if state.tool_execution_records:
            state.tool_execution_records[-1].metadata.update(summary_payload)

        trace_dicts = [rec.model_dump() for rec in state.tool_execution_records]

        return {
            "reply": final_reply,
            "citations": citations,
            "agent_trace": trace_dicts,
            "proposed_action": proposed_action,
            "llm_mode": llm_status,
            "orchestration_summary": summary_payload,
        }

    def _append_skip_record(
        self,
        state: OrchestrationState,
        agent_key: str,
        tool_name: str,
        reason: str,
    ) -> None:
        state.tool_execution_records.append(
            ToolExecutionRecord(
                execution_id=f"ag_skip_{uuid.uuid4().hex[:8]}",
                step_order=len(state.tool_execution_records) + 1,
                kind="agent",
                agent=agent_key,
                tool=tool_name,
                status="skipped",
                skip_reason=reason,
                started_at=_utc_iso(),
                ended_at=_utc_iso(),
                duration_ms=0.0,
            )
        )

    def _execute_single_agent(
        self,
        db: Session,
        user_id: int,
        agent_key: AgentName,
        plan: StructuredPlan,
        primary_exam: str,
        state: OrchestrationState,
        cache: dict[str, dict[str, Any]],
    ) -> None:
        started_iso = _utc_iso()
        t0 = time.perf_counter()
        target_exams = plan.mentioned_examinations or [primary_exam]
        eff_exam = plan.primary_examination or target_exams[0]
        constraints = plan.preparation_constraints
        exec_id = f"ag_{uuid.uuid4().hex[:8]}"

        try:
            if agent_key == "StudentAnalysisAgent":
                out = StudentAnalysisAgent().run(
                    db=db,
                    user_id=user_id,
                    exam_id=eff_exam,
                    registry=self.registry,
                    state=state,
                    cache=cache,
                    requested_tools=plan.required_tools,
                )
            elif agent_key == "ExamIntelligenceAgent":
                out = ExamIntelligenceAgent().run(
                    db=db,
                    query=state.query,
                    exam_ids=target_exams,
                    user_id=user_id,
                    registry=self.registry,
                    state=state,
                    cache=cache,
                    requested_tools=plan.required_tools,
                )
            elif agent_key == "PerformanceDiagnosisAgent":
                out = PerformanceDiagnosisAgent().run(
                    db=db,
                    user_id=user_id,
                    exam_id=eff_exam,
                    registry=self.registry,
                    state=state,
                    cache=cache,
                    requested_tools=plan.required_tools,
                )
            elif agent_key == "KnowledgeTransferAgent":
                src = eff_exam
                tgt = plan.target_or_alternative_examination
                if not tgt or tgt == src:
                    others = [e for e in target_exams if e != src]
                    tgt = others[0] if others else ("TNPSC_GRP1" if src != "TNPSC_GRP1" else "SSC_CGL")
                out = KnowledgeTransferAgent().run(
                    db=db,
                    user_id=user_id,
                    source_exam_id=src,
                    target_exam_id=tgt,
                    registry=self.registry,
                    state=state,
                    cache=cache,
                    extra_exam_ids=target_exams if len(target_exams) > 2 else None,
                )
            elif agent_key == "PathwayPlanningAgent":
                feasibility_only = plan.query_category in ("preparation_feasibility_analysis", "preparation_time_feasibility")
                switch_tgt = plan.target_or_alternative_examination or (
                    target_exams[-1] if ("switch" in state.query.lower() or len(target_exams) >= 2) else eff_exam
                )
                out = PathwayPlanningAgent().run(
                    db=db,
                    user_id=user_id,
                    switch_exam_id=switch_tgt,
                    hours=constraints.daily_hours,
                    days_per_week=constraints.days_per_week,
                    duration_months=constraints.timeline_months,
                    focus_subject_ids=constraints.focus_subjects or None,
                    feasibility_only=feasibility_only,
                    registry=self.registry,
                    state=state,
                    cache=cache,
                )
            elif agent_key == "StudyOptimizationAgent":
                out = StudyOptimizationAgent().run(
                    db=db,
                    user_id=user_id,
                    exam_id=eff_exam,
                    daily_hours=constraints.daily_hours,
                    days_per_week=constraints.days_per_week,
                    focus_subjects=constraints.focus_subjects or None,
                    registry=self.registry,
                    state=state,
                    cache=cache,
                )
            else:
                raise ValueError(f"Unsupported agent key '{agent_key}'")

            state.agent_outputs[agent_key] = out
            state.retrieved_evidence[agent_key] = out.get("data", {})
            for lim in out.get("limitations", []):
                if lim not in state.limitations:
                    state.limitations.append(lim)
            for miss in out.get("missing_evidence", []):
                if miss not in state.missing_evidence:
                    state.missing_evidence.append(miss)

            state.tool_execution_records.append(
                ToolExecutionRecord(
                    execution_id=exec_id,
                    step_order=len(state.tool_execution_records) + 1,
                    kind="agent",
                    agent=out["agent"],
                    tool=out.get("tool_used", agent_key),
                    status=out.get("status", "completed"),
                    input_summary=f"exam={eff_exam}, exams={target_exams}",
                    output_summary=out.get("summary", ""),
                    started_at=started_iso,
                    ended_at=_utc_iso(),
                    duration_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                    evidence_references=out.get("evidence_refs", []),
                    metadata={"rationale": state.selection_rationale.get(agent_key, "")},
                )
            )
        except Exception as exc:
            err = f"{agent_key} execution error: {exc}"
            state.errors.append(err)
            state.tool_execution_records.append(
                ToolExecutionRecord(
                    execution_id=exec_id,
                    step_order=len(state.tool_execution_records) + 1,
                    kind="agent",
                    agent=agent_key,
                    tool=agent_key,
                    status="failed",
                    input_summary=f"exam={eff_exam}",
                    started_at=started_iso,
                    ended_at=_utc_iso(),
                    duration_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                    error_details=err,
                )
            )

    def _build_validated_proposal(
        self,
        db: Session,
        user_id: int,
        plan: StructuredPlan,
        primary_exam: str,
        profile: Optional[StudentProfile],
        state: OrchestrationState,
        cache: dict[str, dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        ac = state.action_constraints
        if ac.investigation_only or not ac.plan_generation_allowed or not ac.plan_preview_allowed or not ac.plan_activation_allowed:
            return None
        if "StudyOptimizationAgent" not in state.agent_outputs:
            return None
        so_out = state.agent_outputs["StudyOptimizationAgent"]
        if so_out.get("status") == "skipped":
            return None
        preview = so_out.get("preview_plan") or {}
        if not preview:
            return None

        target_for_plan = preview.get("exam_id") or plan.primary_examination or primary_exam
        eff_hrs = preview.get("daily_hours") or plan.preparation_constraints.daily_hours or (profile.daily_study_hours if profile else 4.5)
        candidate = {
            "proposal_type": "apply_study_plan",
            "label": f"Generate & Activate {target_for_plan} Study Plan ({eff_hrs}h/day)",
            "description": "Applies the optimized weekly study schedule based on your current gaps and retention queue.",
            "payload": {"exam_id": target_for_plan, "daily_hours": float(eff_hrs)},
        }
        val_res = self.registry.execute(
            db=db,
            user_id=user_id,
            tool_name="validate_proposed_action",
            raw_args={
                "proposal_type": candidate["proposal_type"],
                "payload": candidate["payload"],
                "plan_activation_allowed": ac.plan_activation_allowed,
                "modification_allowed": ac.modification_allowed,
            },
            state=state,
            agent_name="Orchestrator",
            existing_cache=cache,
        )
        if val_res.ok and val_res.data.get("valid"):
            return candidate
        return None

    def _compose_grounded_reply(self, state: OrchestrationState) -> str:
        plan = state.structured_intent
        outputs = state.agent_outputs
        ac = state.action_constraints
        cat = plan.query_category if plan else "general_counselling"
        lines: list[str] = []

        if plan and plan.clarification_required and plan.clarification_question:
            lines.append(f"### Clarification / Scope Notice\n{plan.clarification_question}\n")

        if plan and plan.requires_verified_exam_info and any(
            k in state.query.lower() for k in ("date", "vacancy", "vacancies", "notification", "cutoff")
        ):
            lines.append(
                "**Verification Notice:** GovPath AI does not fabricate or assume live examination dates, "
                "vacancy counts, or cycle-specific notification cutoffs. Those live values are unavailable "
                "in local storage; please verify active cycle details directly from the official portals listed in citations."
            )
            lines.append("")

        executed_labels = [
            f"{out.get('agent')} ({out.get('tool_used')})"
            for out in outputs.values()
            if out.get("status") != "skipped"
        ]
        planner_desc = (
            f"deterministic_fallback (LLM unavailable/failed: {state.llm_error})"
            if state.fallback_used and state.llm_error
            else (plan.planner_mode if plan else "deterministic_fallback")
        )
        lines.append(
            f"### Analysis Overview\n"
            f"- **Objective:** {plan.user_objective if plan else state.query}\n"
            f"- **Workflow Category:** `{cat}` *(Planner: {planner_desc})*\n"
            f"- **Executed Agents & Tools:** {', '.join(executed_labels) if executed_labels else 'None'}"
        )
        if ac.explicit_user_prohibitions:
            lines.append(
                f"- **Enforced Action Restrictions:** Study plan generation={ac.plan_generation_allowed}, "
                f"Activation={ac.plan_activation_allowed}, Investigation-only={ac.investigation_only} "
                f"*(Honoring: {', '.join(ac.explicit_user_prohibitions)})*"
            )
            if any("Conflicting directives" in r for r in ac.prohibition_reasons):
                lines.append(
                    "- **Conflicting Request Notice:** Your prompt contained both a prohibition against creating a "
                    "study plan/timetable and a request to generate one. The explicit prohibition takes precedence, "
                    "so analysis was completed without generating or activating any plan."
                )

        sa = outputs.get("StudentAnalysisAgent")
        if sa:
            r = sa["readiness"]
            prof = sa["profile_summary"]
            ev_cls = sa.get("evidence_classification", {})
            assessments_done = r.get("assessments_completed", 0)
            demo_tag = " *(based on initial demonstration records)*" if r.get("has_only_demo_data") else ""

            lines.append(
                f"\n### Stored Preparation & Evidence Summary for {prof['display_name']}\n"
                f"- **Profile Target:** {prof['primary_target_exam']} (Analyzed: {r['exam_id']}) | "
                f"**User-Reported Availability:** {prof['daily_hours']}h/day × {prof['days_per_week']} days/week ({prof['timeline_months']} months)"
            )

            if assessments_done == 0:
                lines.append(
                    "- **Verified Assessment Evidence:** **0 completed assessments** and **0 competency evidence records** stored. "
                    "Measured performance metrics (`readiness_index`: 0.0%, `competency_coverage`: 0.0%, `accuracy`: 0.0%, `retention_index`: 0.0%) "
                    "reflect **unavailable assessment measurements**, NOT that you have zero real-world knowledge or cannot clear the exam."
                )
            else:
                ret_sum = (sa.get("retention") or {}).get("summary", {})
                ret_detail = (
                    f"; Retention tracker: {ret_sum.get('overdue_count', 0)} overdue, {ret_sum.get('due_soon_count', 0)} due soon"
                    if ret_sum
                    else ""
                )
                lines.append(
                    f"- **Verified Assessment Evidence{demo_tag}:** **{assessments_done} completed assessment(s)** "
                    f"({ev_cls.get('total_evidence_records', 0)} competency evidence record(s)) | "
                    f"**Model Readiness Alignment:** **{r['readiness_index']}%** "
                    f"(Distinct Coverage: {r['competency_coverage']}%, Mean Attempt Accuracy: {r['accuracy']}%, 14-Day Recency Retention: {r['retention_index']}%{ret_detail})\n"
                    f"- *Basis note: Readiness measures weighted assessment alignment against target exam depth, not an official pass probability. "
                    f"Multiple observations on one competency raise confidence without inflating distinct-topic coverage.*"
                )

            act = ev_cls.get("stored_activity", {})
            plan_desc = (
                f"Yes — pre-existing stored plan for {act.get('active_plan_exam')} ({act.get('total_tasks', 0)} tasks, {act.get('completed_tasks', 0)} completed)"
                if act.get("has_active_study_plan")
                else "None stored"
            )
            plan_action_note = (
                "No study plan was created, modified, or activated during this investigation."
                if (ac.investigation_only or not ac.plan_generation_allowed)
                else "Plan preview authorized."
            )
            lines.append(
                f"- **Existing Stored Study Plan (Read-Only Check):** {plan_desc}. *{plan_action_note}*"
            )

            # Progress Monitoring: chronological attempt trajectory & competency trends
            if cat == "progress_monitoring" or (plan and "progress_monitoring" in plan.secondary_categories):
                recent_atts = act.get("recent_attempts", [])
                lines.append("\n### Progress & Performance Trend Comparison")
                if len(recent_atts) >= 2:
                    chrono = sorted(recent_atts, key=lambda a: (a.get("completed_at") or "", a.get("id") or 0))
                    first_a, last_a = chrono[0], chrono[-1]
                    score_delta = round(float(last_a.get("score_percent", 0.0)) - float(first_a.get("score_percent", 0.0)), 1)
                    att_summary = "; ".join(
                        f"{a['title']} ({a['score_percent']}% score, {a['accuracy_percent']}% acc)"
                        for a in chrono[-4:]
                    )
                    lines.append(
                        f"- **Attempt Trajectory ({len(chrono)} recent completed):** {att_summary} "
                        f"→ Net score change: **{score_delta:+.1f} pts**"
                    )
                elif len(recent_atts) == 1:
                    only_a = recent_atts[0]
                    lines.append(
                        f"- **Attempt Trajectory (Insufficient Prior History):** Only 1 completed attempt ({only_a['title']}, "
                        f"{only_a['score_percent']}%). Longitudinal progress comparison requires at least 2 completed assessments."
                    )
                else:
                    lines.append(
                        "- **Attempt Trajectory (Insufficient Evidence):** 0 completed assessments recorded; trend comparison is unavailable."
                    )

                ret_items = (sa.get("retention") or {}).get("items", [])
                if ret_items:
                    improving = [i for i in ret_items if i.get("retention_trend") == "Improving"]
                    declining = [i for i in ret_items if i.get("retention_trend") == "Declining"]
                    stable = [i for i in ret_items if i.get("retention_trend") == "Stable"]
                    single_obs = [i for i in ret_items if i.get("retention_trend") == "Single Observation"]
                    needs_base = [i for i in ret_items if i.get("retention_trend") == "Needs Baseline"]

                    def _fmt_trend(items_list: list[dict[str, Any]]) -> str:
                        parts = []
                        for it in items_list[:5]:
                            prev_s = it.get("previous_performance")
                            curr_s = it.get("current_estimate")
                            if prev_s is not None:
                                parts.append(f"{it['topic_name']} ({prev_s}% → {curr_s}%)")
                            else:
                                parts.append(f"{it['topic_name']} ({curr_s}%)")
                        return ", ".join(parts)

                    lines.append(
                        f"- **Improving Competencies ({len(improving)}):** "
                        + (_fmt_trend(improving) + " *(gaining strength — do not treat as weak)*" if improving else "None yet with >= +5% gain across repeat observations")
                    )
                    lines.append(
                        f"- **Declining Competencies ({len(declining)}):** "
                        + (_fmt_trend(declining) if declining else "None with >= 5% decline")
                    )
                    lines.append(
                        f"- **Stable Competencies ({len(stable)}):** "
                        + (_fmt_trend(stable) if stable else "None with repeat observations within +/-5%")
                    )
                    lines.append(
                        f"- **Insufficient Trend History ({len(single_obs)} single-observation, {len(needs_base)} unassessed):** "
                        "Cannot classify trend direction without >= 2 dated observations."
                    )

                nxt = sa.get("next_assessment_recommendation")
                if nxt:
                    lines.append(
                        f"\n### Next Priority Comparison & Assessment Recommendation\n"
                        f"- **Top Priority:** {nxt['title']} (`{nxt['recommended_assessment_type']}`, "
                        f"{nxt['recommended_question_count']} from {nxt['available_questions']} matching Q(s)) — {nxt['basis']}"
                    )
                    if nxt.get("candidate_alternatives"):
                        alt_str = "; ".join(
                            f"{alt['title']} (score {alt['priority_score']}, {alt['recommended_question_count']}/{alt['available_questions']} Qs — {alt['basis']})"
                            for alt in nxt["candidate_alternatives"]
                        )
                        lines.append(f"- **Alternative Priorities Evaluated:** {alt_str}")

            # Read-Only Existing Study Plan Review (e.g. E4 'do not change existing plan')
            ex_plan = sa.get("existing_plan_tasks") or {}
            if ex_plan and not (ac.plan_generation_allowed and ac.plan_preview_allowed):
                if ex_plan.get("has_active_plan"):
                    task_list = ex_plan.get("tasks", [])
                    sample_ex = "\n".join(
                        f"  - Day {t['day_index']}: **{t['title']}** ({t['duration_minutes']} mins, status: `{t['status']}`)"
                        for t in task_list[:5]
                    )
                    lines.append(
                        f"\n### Existing Study Plan Review (Read-Only — Unchanged)\n"
                        f"- **Stored Active Plan:** {ex_plan.get('title')} ({ex_plan.get('exam_id')} @ {ex_plan.get('daily_hours')}h/day × "
                        f"{ex_plan.get('days_per_week')}d/wk; {ex_plan.get('completed_count', 0)}/{ex_plan.get('task_count', 0)} tasks completed). "
                        f"*Existing plan records were NOT modified or reactivated.*\n{sample_ex}"
                    )
                    recs = []
                    if sa.get("overdue_revisions"):
                        recs.append(f"Prioritize overdue retention review ({', '.join(r['topic_name'] for r in sa['overdue_revisions'][:3])}).")
                    if sa.get("top_gaps"):
                        recs.append(f"Allocate focus blocks to top measured gaps ({', '.join(g['topic_name'] for g in sa['top_gaps'][:3])}).")
                    if recs:
                        lines.append(f"- **Recommended Improvements (Advisory Only):** {' '.join(recs)}")
                else:
                    lines.append(
                        "\n### Existing Study Plan Review (Read-Only — Unchanged)\n"
                        "- No active study plan is currently stored in the database; zero records were modified."
                    )

            # Detailed Evidence Investigation breakdown
            if cat in ("preparation_evidence_investigation", "diagnostic_assessment_recommendation", "readiness_evaluation", "competency_gap_analysis") or "evidence" in state.query.lower():
                assessed = ev_cls.get("assessed_competencies", [])
                total_assessed = ev_cls.get("assessed_competencies_count", len(assessed))
                missing_c = ev_cls.get("missing_competencies", [])
                total_missing = ev_cls.get("missing_competencies_count", len(missing_c))
                if assessed:
                    top_n = min(5, len(assessed))
                    ass_str = "\n".join(
                        f"  - **{c['topic_name']}** ({c['subject_name']}): Measured score {c['current_evidence']}% vs required {c['required_level']} ({c['evidence_count']} observation(s))"
                        for c in assessed[:5]
                    )
                    header_label = (
                        f"Showing Top {top_n} of {total_assessed} total"
                        if total_assessed > top_n
                        else f"{total_assessed} total"
                    )
                    lines.append(f"\n### Competencies With Recorded Evidence ({header_label})\n{ass_str}")
                    if len(assessed) > 5:
                        rem_str = ", ".join(
                            f"{c['topic_name']} ({c['current_evidence']}%, {c['evidence_count']} obs)"
                            for c in assessed[5:]
                        )
                        lines.append(f"- **Remaining {len(assessed) - 5} Recorded Competencies:** {rem_str}")
                else:
                    lines.append(
                        f"\n### Competencies With Recorded Evidence (0 total)\n"
                        f"- **None recorded yet.** All {total_missing} competencies for {r['exam_id']} currently lack assessment evidence."
                    )

                if missing_c:
                    miss_str = "\n".join(
                        f"  - **{c['topic_name']}** ({c['subject_name']}): Weightage {c['weightage_percent']}%, Model required depth {c['required_level']} *(Unassessed — 0 evidence records; does not imply zero knowledge)*"
                        for c in missing_c[:5]
                    )
                    miss_label = (
                        f"Showing {min(5, len(missing_c))} of {total_missing} total"
                        if total_missing > 5
                        else f"{total_missing} total"
                    )
                    lines.append(
                        f"\n### Competencies With Insufficient / Missing Evidence ({miss_label})\n{miss_str}"
                    )

                nxt = sa.get("next_assessment_recommendation")
                if nxt:
                    lines.append(
                        f"\n### Most Useful Next Assessment\n"
                        f"- **Recommended:** {nxt['title']} (`{nxt['recommended_assessment_type']}`, "
                        f"{nxt['recommended_question_count']} recommended from {nxt['available_questions']} available matching question(s), "
                        f"~{nxt.get('estimated_minutes', nxt['recommended_question_count'])} mins)\n"
                        f"- **Basis:** {nxt['basis']}\n"
                        f"- **Why:** {nxt['rationale']}"
                    )
                    if nxt.get("candidate_alternatives"):
                        alt_str = "; ".join(
                            f"{alt['title']} (score {alt['priority_score']}, {alt['recommended_question_count']}/{alt['available_questions']} Qs — {alt['basis']})"
                            for alt in nxt["candidate_alternatives"]
                        )
                        lines.append(f"- **Alternative Candidates Evaluated:** {alt_str}")
            elif sa.get("top_gaps") and assessments_done > 0:
                gap_list = "\n".join(
                    f"  - **{g['topic_name']}** ({g['subject_name']}): Required {g['required_level']} vs Current {g['current_evidence']} → **Gap {g['gap']} ({g['priority']})**"
                    for g in sa["top_gaps"][:4]
                )
                lines.append(f"\n### Priority Competency Gaps\n{gap_list}")

            revs = sa.get("overdue_revisions", [])
            if revs and assessments_done > 0 and (cat in ("retention_analysis", "compound_multi_intent", "study_plan_generation", "study_plan_modification") or "revise" in state.query.lower() or "forget" in state.query.lower()):
                rev_list = "\n".join(
                    f"  - **{rv['topic_name']}** ({rv['subject_name']}) — *{rv['revision_status']}* (Current estimate: {rv['current_estimate']}%)"
                    for rv in revs[:4]
                )
                lines.append(f"\n### Retention & Revision Queue\n{rev_list}")

        if "KnowledgeTransferAgent" in outputs:
            kt = outputs["KnowledgeTransferAgent"]
            cc = kt.get("classification_counts", {})
            lines.append(
                f"\n### Knowledge Transfer & Structural Comparison ({kt['source_exam']} → {kt['target_exam']})\n"
                f"- **1. Theoretical Structural Syllabus Overlap:** **{kt['structural_overlap_percent']}%** of {kt['target_exam']} competencies "
                f"({kt.get('shared_competency_count', 0)} shared competencies in the exam graph; {kt.get('target_only_competency_count', 0)} target-only).\n"
                f"- **2. Verified Individual Evidence:** {kt.get('assessments_completed', 0)} completed assessment(s); "
                f"{kt.get('evidence_backed_shared_count', 0)} shared competenc(ies) have recorded assessment evidence, "
                f"{kt.get('unassessed_shared_count', 0)} shared competenc(ies) are unassessed "
                f"(verified mastery-only transfer alignment: **{kt.get('verified_mastery_transfer_percent', 0.0)}%**).\n"
                f"- **3. {kt.get('transfer_index_label', 'Model-Estimated Transfer Index')}:** **{kt['effective_transfer_index']}%**\n"
                f"  - *Disclosure:* {kt.get('transfer_index_disclosure')}\n"
                f"- **Model Classification Breakdown:** {cc.get('Fully Transferable', 0)} Fully Transferable, "
                f"{cc.get('Partially Transferable', 0)} Partially Transferable, "
                f"{cc.get('Requires Reinforcement', 0)} Require Reinforcement, "
                f"{cc.get('Not Covered', 0)} New / Target-Only\n"
                f"- **Model-Estimated Additional Bridge Effort:** ~**{kt['estimated_additional_hours']} hours** *(model approximation from remaining depth gaps)*"
            )
            if kt.get("shared_competencies_sample"):
                sh_names = ", ".join(s["competency_name"] for s in kt["shared_competencies_sample"][:4])
                lines.append(f"- **Shared Exam Competencies (Syllabus Level):** {sh_names}")
            if kt.get("target_only_competencies_sample"):
                new_names = ", ".join(c["competency_name"] for c in kt["target_only_competencies_sample"][:4])
                lines.append(f"- **Additional Target-Only Skills Needed:** {new_names}")
            elif kt.get("top_missing_or_reinforce"):
                top_items = ", ".join(f"{c['competency_name']} ({c['classification']})" for c in kt["top_missing_or_reinforce"][:3])
                lines.append(f"- **Key Bridge Priorities:** {top_items}")

        if "PerformanceDiagnosisAgent" in outputs:
            pd_out = outputs["PerformanceDiagnosisAgent"]
            if not pd_out.get("has_data"):
                lines.append(
                    "\n### Performance & Error Diagnosis\n"
                    "No completed assessment attempts found yet. Complete a diagnostic or topic quiz first so weaknesses can be diagnosed from actual answer evidence."
                )
            else:
                err_str = ", ".join(f"{k}: {v}" for k, v in pd_out.get("error_breakdown", {}).items()) or "No errors recorded"
                lines.append(
                    f"\n### Performance & Error Diagnosis\n"
                    f"- **Recorded Mistakes Analyzed:** {pd_out['total_mistakes']} ({err_str})"
                )
                if pd_out.get("repeated_weak"):
                    rep_str = ", ".join(f"{w['topic_name']} ({w['error_count']} errors)" for w in pd_out["repeated_weak"][:3])
                    lines.append(f"- **Repeated Weak Topics:** {rep_str}")
                for rec in pd_out.get("recommendations", [])[:3]:
                    lines.append(f"- {rec}")

        if "PathwayPlanningAgent" in outputs:
            pp = outputs["PathwayPlanningAgent"]
            if pp.get("top_pathways"):
                p_lines = "\n".join(
                    f"  - **{p['short_name']}** ({p['role']}) — Suitability: **{p['suitability_score']}/100**, Readiness: {p['readiness_index']}%, Model Transfer: {p['transfer_from_primary_percent']}%"
                    for p in pp["top_pathways"][:3]
                )
                lines.append(f"\n### Recommended Exam Pathways\n{p_lines}")
            if pp.get("simulation"):
                sim = pp["simulation"]
                bc = sim["baseline_comparison"]
                wa = sim["workload_assessment"]
                lines.append(
                    f"\n### Preparation Feasibility Analysis ({sim['scenario']['target_exam_id']} @ {sim['scenario']['daily_hours']}h/day × {sim['scenario']['days_per_week']} days/week over {sim['scenario']['duration_months']} months)\n"
                    f"- **Available Capacity vs Model-Required Workload:** **{wa['total_available_hours']}h available** vs **~{wa['estimated_required_hours']}h estimated required** "
                    f"(Capacity-to-need ratio: **{wa['capacity_to_need_ratio']}**) → Feasibility: **{wa['feasibility_status']}**\n"
                    f"- **Current vs Projected Model Alignment:** {bc['current_readiness_index']}% → **{bc['projected_readiness_index']}%** ({bc['readiness_delta']:+} pts)"
                )
                for rsk in pp.get("feasibility_risks", []):
                    lines.append(f"- **Risk / Uncertainty:** {rsk}")
                if pp.get("feasibility_assumptions"):
                    lines.append(f"- **Model Assumption:** {pp['feasibility_assumptions'][0]}")

        if "StudyOptimizationAgent" in outputs and outputs["StudyOptimizationAgent"].get("status") == "completed" and ac.plan_generation_allowed and ac.plan_preview_allowed:
            so_out = outputs["StudyOptimizationAgent"]
            sp = so_out.get("preview_plan", {})
            ex_sp = so_out.get("existing_plan", {})
            if sp and sp.get("tasks"):
                sample_tasks = "\n".join(
                    f"  - Day {t['day_index']}: **{t['title']}** ({t['duration_minutes']} mins)"
                    for t in sp["tasks"][:4]
                )
                saved_state = (
                    f"Active Saved Plan in DB: {ex_sp.get('title')} ({ex_sp.get('task_count', 0)} tasks) — unchanged until you confirm."
                    if ex_sp.get("has_active_plan")
                    else "Saved / Active Plan in DB: None saved or activated yet."
                )
                lines.append(
                    f"\n### Proposed Adaptive Study Plan ({sp['daily_hours']}h/day — Preview Only, Not Saved or Active)\n"
                    f"- **Plan Status Distinction:** Proposed Preview Plan (unpersisted in-memory draft) | {saved_state}\n"
                    f"- **Rationale:** {sp['generation_rationale']}\n{sample_tasks}\n"
                    + (
                        "*(Review this proposed plan above and click Confirm & Apply below only when ready to save and activate it.)*"
                        if state.proposed_action
                        else "*(Preview only — plan saving and activation are disabled per your request.)*"
                    )
                )

        if "ExamIntelligenceAgent" in outputs:
            ei = outputs["ExamIntelligenceAgent"]
            if ei.get("exam_summaries") and "KnowledgeTransferAgent" not in outputs and "StudyOptimizationAgent" not in outputs and "PathwayPlanningAgent" not in outputs:
                ex0 = ei["exam_summaries"][0]
                lines.append(
                    f"\n### Verified Exam Reference: {ex0['name']}\n"
                    f"- **Conducting Authority:** {ex0['authority']}\n"
                    f"- **Stages:** {' → '.join(ex0['stages'])}\n"
                    f"- **Eligibility Summary:** {ex0['eligibility']}"
                )

        notes = list(dict.fromkeys(state.missing_evidence + state.limitations))
        if notes:
            lines.append("\n### Evidence Limitations & Uncertainty\n" + "\n".join(f"- {n}" for n in notes[:5]))

        next_action = self._recommend_next_action(state)
        lines.append(f"\n### Next Recommended Action\n- {next_action}")

        return "\n".join(lines)

    def _recommend_next_action(self, state: OrchestrationState) -> str:
        outputs = state.agent_outputs
        if state.structured_intent and state.structured_intent.clarification_required:
            return "Specify one of the supported examinations or clarify your target objective so specialized tools can run deeper analysis."
        if state.proposed_action:
            return f"Review and confirm the proposed action: **{state.proposed_action['label']}**."
        sa = outputs.get("StudentAnalysisAgent", {})
        nxt = sa.get("next_assessment_recommendation") if sa else None
        if nxt:
            return f"Take **{nxt['title']}** (`{nxt['recommended_assessment_type']}`, {nxt['recommended_question_count']} questions) to convert missing assumptions into measured evidence."
        if sa and sa.get("readiness", {}).get("assessments_completed", 0) == 0:
            return "Take a baseline Diagnostic Assessment on your primary target exam to establish verified competency scores."
        if "KnowledgeTransferAgent" in outputs:
            kt = outputs["KnowledgeTransferAgent"]
            return f"Establish verified baseline evidence on shared competencies and begin bridging the target-only competencies for **{kt['target_exam']}**."
        if "PathwayPlanningAgent" in outputs and outputs["PathwayPlanningAgent"].get("simulation"):
            sim = outputs["PathwayPlanningAgent"]["simulation"]
            return f"Run a baseline diagnostic on **{sim['scenario']['target_exam_id']}** to refine the workload estimate before building a timetable."
        if sa and sa.get("overdue_revisions"):
            top_rev = sa["overdue_revisions"][0]["topic_name"]
            return f"Run a 10-minute spaced retrieval quiz on **{top_rev}** before adding new syllabus topics."
        return "Target your highest-priority competency gap with a focused practice quiz to raise verified alignment."
