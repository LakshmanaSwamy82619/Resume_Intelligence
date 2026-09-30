"""
Agent orchestration (Section 17).

    Job Requirement -> Candidate Retrieval -> Candidate Matching Agent
    -> Skill Gap Agent -> Qualification Agent -> Evidence Retrieval
    -> Explainability/Validation Agent -> Final Ranking

The handoffs are explicit typed envelopes: each receiver validates the
sender, recipient, and payload before it runs. The envelope history is
retained on the per-candidate state and summarized in persisted search
traces. This is in-process sequential agent-to-agent communication; the
pipeline does not claim to implement Google's remote A2A protocol.

The graph has no branching or dynamic routing, so plain async composition
is a deliberate fit. A graph engine can be added if future flows need
branching, retries, or remote agents.

If a future requirement needs real branching/looping (e.g. an agent that
can request the retrieval stage fetch more evidence and re-run), swapping
this module for a LangGraph `StateGraph` over the same `AgentState` is a
localized change -- `AgentState` was designed as a plain dataclass for
exactly that portability.
"""
from __future__ import annotations

from app.agents.matching_agent import run_candidate_matching_agent
from app.agents.qualification_agent import run_qualification_agent
from app.agents.skill_gap_agent import run_skill_gap_agent
from app.agents.explainability_agent import run_explainability_agent
from app.agents.state import AgentState
from app.providers.llm.chain import LLMProviderChain


async def run_agent_pipeline(state: AgentState, llm_chain: LLMProviderChain | None) -> AgentState:
    state.matching_result = run_candidate_matching_agent(state)
    state.mark_agent_complete("candidate_matching")

    handoff = state.handoff_to(
        "skill_gap", {"matching_result": state.matching_result},
        ["matched_requirements", "missing_requirements", "project_relevance"],
    )
    state.skill_gap_result = run_skill_gap_agent(state, handoff)
    state.mark_agent_complete("skill_gap")

    handoff = state.handoff_to(
        "qualification",
        {"matching_result": state.matching_result, "skill_gap_result": state.skill_gap_result},
        ["requirement_findings", "skill_alignment_score"],
    )
    state.qualification_result = run_qualification_agent(state, handoff)
    state.mark_agent_complete("qualification")

    handoff = state.handoff_to(
        "explainability",
        {
            "matching_result": state.matching_result,
            "skill_gap_result": state.skill_gap_result,
            "qualification_result": state.qualification_result,
        },
        ["validated_findings", "qualification_assessment", "skill_alignment_score"],
    )
    state.explainability_result = await run_explainability_agent(state, llm_chain, handoff)
    state.mark_agent_complete("explainability")
    return state
