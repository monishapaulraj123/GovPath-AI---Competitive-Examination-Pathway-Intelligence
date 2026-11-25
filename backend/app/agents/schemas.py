"""
Validated Pydantic schemas for Phase 1 LLM-assisted Agent Orchestration,
Structured Intent Planning, Tool Registry, Agent Outputs, Shared State, and Execution Trace.
"""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator

IntentCategory = Literal[
    "student_preparation_analysis",
    "readiness_evaluation",
    "performance_diagnosis",
    "competency_gap_analysis",
    "retention_analysis",
    "knowledge_transfer",
    "examination_comparison",
    "alternative_examination_pathway",
    "study_plan_generation",
    "study_plan_optimization",
    "preparation_time_feasibility",
    "exam_intelligence_retrieval",
    "assessment_preparation",
    "progress_analysis",
    "multi_objective_preparation_analysis",
    "general_counselling",
    "compound_multi_intent",
]

AgentName = Literal[
    "StudentAnalysisAgent",
    "ExamIntelligenceAgent",
    "PerformanceDiagnosisAgent",
    "KnowledgeTransferAgent",
    "PathwayPlanningAgent",
    "StudyOptimizationAgent",
]

ExecutionStatus = Literal["planned", "running", "completed", "failed", "skipped"]

WorkflowStatus = Literal[
    "initialized",
    "planning",
    "executing",
    "evaluating",
    "completed",
    "completed_with_limitations",
    "clarification_needed",
    "failed",
]


class PreparationConstraints(BaseModel):
    daily_hours: Optional[float] = Field(default=None, ge=0.5, le=16.0)
    days_per_week: Optional[int] = Field(default=None, ge=1, le=7)
    timeline_months: Optional[int] = Field(default=None, ge=1, le=60)
    focus_subjects: list[str] = Field(default_factory=list)
    notes: str = Field(default="")


class StructuredPlan(BaseModel):
    user_objective: str = Field(..., min_length=1, max_length=600)
    query_category: IntentCategory = Field(default="general_counselling")
    secondary_categories: list[IntentCategory] = Field(default_factory=list)
    primary_examination: Optional[str] = Field(default=None)
    target_or_alternative_examination: Optional[str] = Field(default=None)
    mentioned_examinations: list[str] = Field(default_factory=list)
    relevant_competencies: list[str] = Field(default_factory=list)
    preparation_constraints: PreparationConstraints = Field(default_factory=PreparationConstraints)
    requested_analysis: list[str] = Field(default_factory=list)
    required_agents: list[AgentName] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    execution_sequence: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    clarification_required: bool = Field(default=False)
    clarification_question: Optional[str] = Field(default=None)
    requires_verified_exam_info: bool = Field(default=False)
    planner_mode: Literal["llm_structured", "deterministic_fallback"] = Field(
        default="deterministic_fallback"
    )
    planner_provider: str = Field(default="deterministic_fallback")
    planner_error: Optional[str] = Field(default=None)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    decision_summary: str = Field(default="")

    @field_validator("user_objective")
    @classmethod
    def strip_objective(cls, v: str) -> str:
        return v.strip() or "Analyze aspirant preparation"


class FollowUpDecision(BaseModel):
    sufficient_evidence: bool = Field(default=True)
    additional_agents: list[AgentName] = Field(default_factory=list)
    additional_tools: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    decision_summary: str = Field(default="")
    stop_reason: str = Field(default="sufficient_evidence")


class ToolExecutionRecord(BaseModel):
    execution_id: str
    step_order: int = Field(ge=1)
    kind: Literal["planner", "agent", "tool", "evaluator", "synthesizer"] = "tool"
    agent: str
    tool: str
    status: ExecutionStatus
    input_summary: str = ""
    output_summary: str = ""
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_ms: Optional[float] = None
    error_details: Optional[str] = None
    evidence_references: list[str] = Field(default_factory=list)
    skip_reason: Optional[str] = None


class AgentOutput(BaseModel):
    agent: str
    agent_key: str
    status: ExecutionStatus = "completed"
    tool_used: str = ""
    tools_used: list[str] = Field(default_factory=list)
    summary: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class CitationItem(BaseModel):
    title: str
    source_name: str
    source_url: str = ""
    verified_status: str = "Verified Reference"
    snippet: str = ""


class ProposedAction(BaseModel):
    proposal_type: Literal["apply_study_plan", "update_target_exam"]
    label: str
    description: str
    payload: dict[str, Any]


class OrchestrationState(BaseModel):
    user_id: int
    query: str
    conversation_context: list[dict[str, str]] = Field(default_factory=list)
    structured_intent: Optional[StructuredPlan] = None
    execution_plan: list[str] = Field(default_factory=list)
    selected_examination_ids: list[str] = Field(default_factory=list)
    selected_agents: list[str] = Field(default_factory=list)
    tool_execution_records: list[ToolExecutionRecord] = Field(default_factory=list)
    agent_outputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    retrieved_evidence: dict[str, Any] = Field(default_factory=dict)
    source_references: list[dict[str, Any]] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    execution_iteration: int = Field(default=0, ge=0)
    llm_calls_used: int = Field(default=0, ge=0)
    tool_calls_used: int = Field(default=0, ge=0)
    estimated_tokens_used: int = Field(default=0, ge=0)
    workflow_status: WorkflowStatus = Field(default="initialized")
    errors: list[str] = Field(default_factory=list)
    final_response: str = Field(default="")
    proposed_action: Optional[dict[str, Any]] = None
