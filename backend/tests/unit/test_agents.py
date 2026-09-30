from app.agents.qualification_agent import run_qualification_agent
from app.agents.skill_gap_agent import run_skill_gap_agent
from app.agents.state import AgentState, CandidateInput, JobRequirementInput


def _make_state(candidate_skills, mandatory_skills, preferred_skills=None, years=None, min_years=None):
    job = JobRequirementInput(
        title="Data Scientist",
        mandatory_skills=mandatory_skills,
        preferred_skills=preferred_skills or [],
        mandatory_other=[],
        preferred_other=[],
        min_experience_years=min_years,
        responsibilities=[],
    )
    candidate = CandidateInput(
        candidate_id="c1",
        full_name="Test Candidate",
        technical_skills=candidate_skills,
        job_titles=[],
        years_of_experience=years,
        experience_entries=[],
        project_entries=[],
        education_entries=[],
        certification_entries=[],
        evidence=[{"field_type": "skill", "field_value": s, "evidence_text": f"Uses {s} daily."} for s in candidate_skills],
    )
    return AgentState(job=job, candidate=candidate)


def test_exact_skill_match():
    state = _make_state(candidate_skills=["python", "sql"], mandatory_skills=["python", "sql"])
    result = run_skill_gap_agent(state)
    assert {f.requirement for f in result.matched_skills} == {"python", "sql"}
    assert result.skill_alignment_score == 1.0


def test_related_skill_is_partial_not_missing():
    state = _make_state(candidate_skills=["pytorch"], mandatory_skills=["tensorflow"])
    result = run_skill_gap_agent(state)
    assert len(result.missing_skills) == 0
    assert len(result.partial_skills) == 1
    assert result.partial_skills[0].note is not None and "pytorch" in result.partial_skills[0].note.lower()


def test_truly_unrelated_skill_is_missing():
    state = _make_state(candidate_skills=["javascript"], mandatory_skills=["python"])
    result = run_skill_gap_agent(state)
    assert len(result.missing_skills) == 1
    assert result.missing_skills[0].requirement == "python"


def test_mandatory_skills_weigh_more_than_preferred_in_alignment_score():
    # Missing a mandatory skill should hurt the score more than missing a
    # preferred one, all else equal (Section 18's mandatory weighting).
    state_missing_mandatory = _make_state(candidate_skills=["sql"], mandatory_skills=["python"], preferred_skills=["sql"])
    state_missing_preferred = _make_state(candidate_skills=["python"], mandatory_skills=["python"], preferred_skills=["sql"])
    result_a = run_skill_gap_agent(state_missing_mandatory)
    result_b = run_skill_gap_agent(state_missing_preferred)
    assert result_b.skill_alignment_score > result_a.skill_alignment_score


def test_qualification_agent_flags_below_minimum_experience():
    state = _make_state(candidate_skills=["python"], mandatory_skills=["python"], years=1.5, min_years=3.0)
    result = run_qualification_agent(state)
    assert "below" in result.years_note.lower()
    assert result.experience_relevance_score < 1.0


def test_qualification_agent_no_requirement_is_neutral():
    state = _make_state(candidate_skills=["python"], mandatory_skills=["python"], years=None, min_years=None)
    result = run_qualification_agent(state)
    assert result.experience_relevance_score == 1.0
