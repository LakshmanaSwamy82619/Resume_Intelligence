"""
Related-skill clusters (Section 15/16).

Used only by the Skill Gap Agent to distinguish a genuinely MISSING skill
from a PARTIAL match where the candidate has clearly adjacent, transferable
experience (e.g. JD wants "TensorFlow", candidate's resume evidences
"PyTorch" -- not an exact match, but strong signal of relevant ML-framework
experience, which is exactly the kind of context-aware judgement Section 15
asks for instead of mechanical exact-keyword matching).

This is a small, explicit, human-reviewable map -- not a learned model --
so every "partial match" the system reports is directly explainable
("candidate has {other_skill}, a related technology").
"""
from __future__ import annotations

SKILL_CLUSTERS: list[set[str]] = [
    {"tensorflow", "pytorch", "keras", "scikit-learn", "xgboost", "lightgbm"},
    {"machine learning", "deep learning", "nlp", "natural language processing", "computer vision", "reinforcement learning"},
    {"postgresql", "postgres", "mysql", "sqlite", "oracle", "sql"},
    {"mongodb", "cassandra", "dynamodb", "redis"},
    {"aws", "azure", "gcp", "google cloud"},
    {"docker", "kubernetes", "helm"},
    {"react", "react.js", "angular", "vue", "vue.js", "next.js"},
    {"django", "flask", "fastapi"},
    {"spring", "spring boot", ".net", "asp.net"},
    {"kafka", "rabbitmq"},
    {"terraform", "ansible", "cloudformation"},
    {"pandas", "numpy", "data analysis", "data science"},
    {"jenkins", "github actions", "gitlab ci", "ci/cd"},
    {"langchain", "langgraph", "llm", "large language models", "generative ai", "transformers", "hugging face"},
]

_CLUSTER_LOOKUP: dict[str, set[str]] = {}
for cluster in SKILL_CLUSTERS:
    for skill in cluster:
        _CLUSTER_LOOKUP[skill] = cluster


def find_related_present_skill(required_skill: str, candidate_skills: set[str]) -> str | None:
    cluster = _CLUSTER_LOOKUP.get(required_skill.lower())
    if not cluster:
        return None
    for candidate_skill in candidate_skills:
        if candidate_skill.lower() in cluster and candidate_skill.lower() != required_skill.lower():
            return candidate_skill
    return None
