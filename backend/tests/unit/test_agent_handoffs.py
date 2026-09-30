from app.agents.orchestrator import run_agent_pipeline
from app.agents.state import AgentState, CandidateInput, JobRequirementInput


def _state():
    return AgentState(
        job=JobRequirementInput(
            title="Backend Engineer", mandatory_skills=["Python"], preferred_skills=[],
            mandatory_other=[], preferred_other=[], min_experience_years=None, responsibilities=[],
        ),
        candidate=CandidateInput(
            candidate_id="candidate-1", full_name="Test Candidate", technical_skills=["Python"],
            job_titles=["Backend Engineer"], years_of_experience=3,
            experience_entries=[], project_entries=[], education_entries=[], certification_entries=[],
            evidence=[{"field_type": "skill", "field_value": "Python", "evidence_text": "Built services with Python."}],
        ),
    )


async def test_pipeline_performs_and_records_each_sequential_handoff():
    state = await run_agent_pipeline(_state(), None)

    assert state.completed_agents == ["candidate_matching", "skill_gap", "qualification", "explainability"]
    assert [(handoff.sender, handoff.recipient) for handoff in state.handoff_history] == [
        ("candidate_matching", "skill_gap"),
        ("skill_gap", "qualification"),
        ("qualification", "explainability"),
    ]
    assert state.handoff_history[0].payload["matching_result"] is state.matching_result
    assert state.handoff_history[1].payload["skill_gap_result"] is state.skill_gap_result
    assert state.handoff_history[2].payload["qualification_result"] is state.qualification_result
    assert [handoff.sequence for handoff in state.handoff_history] == [1, 2, 3]
    assert state.explainability_result is not None


def test_pipeline_rejects_out_of_order_agent_completion():
    state = _state()
    try:
        state.mark_agent_complete("skill_gap")
    except RuntimeError as exc:
        assert "order violation" in str(exc)
    else:
        raise AssertionError("Out-of-order agent completion should be rejected")
