"""
Shared state for the agent pipeline (Section 17).

One AgentState is built per (job_requirements, candidate) pair before
entering the pipeline:

    Candidate Matching Agent -> Skill Gap Agent -> Qualification Agent
    -> Explainability/Validation Agent

Each agent appends a typed result to the state for debugging and evaluation.
Agents exchange typed, validated handoff envelopes through the per-candidate
state; the receiver gets the previous result explicitly. The envelope history
is summarized in saved query traces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobRequirementInput:
    title: str | None
    mandatory_skills: list[str]
    preferred_skills: list[str]
    mandatory_other: list[dict]  # [{"type": "education"/"certification", "value": ...}]
    preferred_other: list[dict]
    min_experience_years: float | None
    responsibilities: list[str]


@dataclass
class CandidateInput:
    candidate_id: str
    full_name: str | None
    technical_skills: list[str]
    job_titles: list[str]
    years_of_experience: float | None
    experience_entries: list[dict]
    project_entries: list[dict]
    education_entries: list[dict]
    certification_entries: list[dict]
    evidence: list[dict]  # [{"field_type","field_value","evidence_text","page_number","source_file"}]


@dataclass
class RequirementFinding:
    requirement: str
    requirement_type: str
    priority: str
    status: str  # matched/partial/missing
    evidence_text: str | None = None
    page_number: int | None = None
    source_file: str | None = None
    note: str | None = None


@dataclass
class MatchingAgentResult:
    matched: list[RequirementFinding] = field(default_factory=list)
    partial: list[RequirementFinding] = field(default_factory=list)
    missing: list[RequirementFinding] = field(default_factory=list)
    project_relevance_score: float = 0.0
    overall_alignment_note: str = ""


@dataclass
class SkillGapAgentResult:
    matched_skills: list[RequirementFinding] = field(default_factory=list)
    partial_skills: list[RequirementFinding] = field(default_factory=list)
    missing_skills: list[RequirementFinding] = field(default_factory=list)
    skill_alignment_score: float = 0.0


@dataclass
class QualificationAgentResult:
    experience_relevance_score: float = 0.0
    education_findings: list[RequirementFinding] = field(default_factory=list)
    certification_findings: list[RequirementFinding] = field(default_factory=list)
    title_relevance_note: str = ""
    years_note: str = ""


@dataclass
class ValidationFlag:
    claim: str
    issue: str


@dataclass
class ExplainabilityAgentResult:
    validation_status: str = "validated"  # validated/flagged
    validation_notes: list[ValidationFlag] = field(default_factory=list)
    evidence_confidence_score: float = 1.0
    explanation_summary: str = ""
    explanation_points: list[str] = field(default_factory=list)
    top_evidence: list[dict] = field(default_factory=list)
    ai_provider: str = "deterministic"
    fallback_used: bool = False
    fallback_reason: str | None = None


@dataclass
class AgentHandoff:
    """Typed in-process A2A envelope passed between sequential agents."""

    sender: str
    recipient: str
    payload: dict[str, Any]
    artifacts: list[str]
    sequence: int


@dataclass
class AgentState:
    job: JobRequirementInput
    candidate: CandidateInput
    reranker_score_normalized: float = 0.0
    matching_result: MatchingAgentResult | None = None
    skill_gap_result: SkillGapAgentResult | None = None
    qualification_result: QualificationAgentResult | None = None
    explainability_result: ExplainabilityAgentResult | None = None
    handoff_history: list[AgentHandoff] = field(default_factory=list)
    incoming_handoff: AgentHandoff | None = None
    completed_agents: list[str] = field(default_factory=list)

    def mark_agent_complete(self, agent_name: str) -> None:
        order = ("candidate_matching", "skill_gap", "qualification", "explainability")
        expected = order[len(self.completed_agents)] if len(self.completed_agents) < len(order) else None
        if agent_name != expected:
            raise RuntimeError(f"Agent pipeline order violation: expected {expected}, got {agent_name}.")
        self.completed_agents.append(agent_name)

    def handoff_to(self, recipient: str, payload: dict[str, Any], artifacts: list[str]) -> AgentHandoff:
        if not self.completed_agents:
            raise RuntimeError("An agent must complete before it can hand off results.")
        sender = self.completed_agents[-1]
        expected = ("candidate_matching", "skill_gap", "qualification", "explainability")
        if recipient not in expected or sender not in expected or expected.index(recipient) != expected.index(sender) + 1:
            raise RuntimeError(f"Invalid agent handoff route: {sender} -> {recipient}.")
        handoff = AgentHandoff(sender, recipient, payload, artifacts, len(self.handoff_history) + 1)
        self.handoff_history.append(handoff)
        self.incoming_handoff = handoff
        return handoff

    def require_handoff(self, sender: str, recipient: str) -> AgentHandoff:
        handoff = self.incoming_handoff
        if handoff is None or (handoff.sender, handoff.recipient) != (sender, recipient):
            raise RuntimeError(f"{recipient} agent requires a valid handoff from {sender}.")
        return handoff

    def handoff_trace(self) -> list[dict[str, Any]]:
        return [
            {"sequence": item.sequence, "from": item.sender, "to": item.recipient, "artifacts": item.artifacts}
            for item in self.handoff_history
        ]
