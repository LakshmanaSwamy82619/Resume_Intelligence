from __future__ import annotations


PROFILE_FIELD_WEIGHTS = {
    "full_name": ("Name", 10),
    "email": ("Email", 10),
    "phone": ("Phone", 5),
    "location": ("Location", 5),
    "summary": ("Professional summary", 10),
    "experience": ("Work experience", 20),
    "technical_skills": ("Skills", 15),
    "education": ("Education", 10),
    "projects": ("Projects", 10),
    "certifications": ("Certifications", 5),
}


def profile_completeness(candidate) -> dict:
    present = {
        "full_name": bool((candidate.full_name or "").strip()),
        "email": bool((candidate.email or "").strip()),
        "phone": bool((candidate.phone or "").strip()),
        "location": bool((candidate.location or "").strip()),
        "summary": bool((candidate.summary or "").strip()),
        "experience": bool(candidate.experience),
        "technical_skills": bool(candidate.technical_skills or candidate.soft_skills),
        "education": bool(candidate.education),
        "projects": bool(candidate.projects),
        "certifications": bool(candidate.certifications),
    }
    score = sum(weight for key, (_, weight) in PROFILE_FIELD_WEIGHTS.items() if present[key])
    completed = [label for key, (label, _) in PROFILE_FIELD_WEIGHTS.items() if present[key]]
    missing = [label for key, (label, _) in PROFILE_FIELD_WEIGHTS.items() if not present[key]]
    return {
        "score": score,
        "completed_fields": completed,
        "missing_fields": missing,
        "complete_fields": len(completed),
        "total_fields": len(PROFILE_FIELD_WEIGHTS),
    }
