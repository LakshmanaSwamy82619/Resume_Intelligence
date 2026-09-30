"""
Structured candidate extraction (Section 6/7).

Produces a StructuredCandidate with every field traceable back to the
exact sentence/line it was derived from (an Evidence). This module is
deliberately deterministic and offline (regex + taxonomy matching over the
already-parsed text) so ingestion never depends on an external AI call --
Section 13 requires ML/local fallback to be sufficient on its own, and
structuring is squarely in that "must always work" path. Retrieval and the
four agents are where deeper semantic reasoning happens on top of this
structured foundation.

Known limitation (documented, not hidden): rule-based extraction will miss
unconventional phrasing (e.g. a skill described only via a project sentence
with no explicit skill-section listing). Section-aware skill matching
across the *entire* resume text (not just the Skills section) mitigates
this partially. A future iteration could add an LLM-assisted structuring
pass as an enhancement with this rule-based pass as its fallback -- the
KeyGateway LLMProvider is already available for that if desired.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ingestion.chunking import Chunk, split_into_sections
from app.ingestion.skills_taxonomy import (
    CERTIFICATION_KEYWORDS,
    DEGREE_KEYWORDS,
    SOFT_SKILLS,
    TECHNICAL_SKILLS,
)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{3,4}")
YEARS_EXPERIENCE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\s*(?:of)?\s*(?:relevant\s+)?experience", re.IGNORECASE
)
DATE_RANGE_RE = re.compile(
    r"(?P<start>(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4}|\d{4})\s*[-–—]\s*"
    r"(?P<end>(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4}|present|current|\d{4})",
    re.IGNORECASE,
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\n])\s+")


@dataclass
class Evidence:
    field_type: str  # skill/experience/project/education/certification/summary
    field_value: str
    evidence_text: str
    page_number: int | None = None
    section: str | None = None


@dataclass
class ExperienceEntry:
    company: str | None
    title: str | None
    start_date: str | None
    end_date: str | None
    duration_years: float | None
    responsibilities_text: str
    evidence_text: str


@dataclass
class ProjectEntry:
    name: str | None
    description: str
    technologies: list[str]
    evidence_text: str


@dataclass
class EducationEntry:
    degree: str | None
    institution: str | None
    field_of_study: str | None
    end_year: str | None
    evidence_text: str


@dataclass
class CertificationEntry:
    name: str
    evidence_text: str


@dataclass
class StructuredCandidate:
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    summary: str | None = None
    technical_skills: list[str] = field(default_factory=list)
    soft_skills: list[str] = field(default_factory=list)
    job_titles: list[str] = field(default_factory=list)
    years_of_experience: float | None = None
    experience: list[ExperienceEntry] = field(default_factory=list)
    projects: list[ProjectEntry] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    certifications: list[CertificationEntry] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


def _find_sentences_with_term(text: str, term: str) -> list[str]:
    sentences = SENTENCE_SPLIT_RE.split(text)
    pattern = re.compile(r"(?<![a-zA-Z0-9])" + re.escape(term) + r"(?![a-zA-Z0-9])", re.IGNORECASE)
    return [s.strip() for s in sentences if s.strip() and pattern.search(s)]


def _extract_name(full_text: str) -> str | None:
    # Heuristic: the first non-empty line that isn't an email/phone/section
    # header and looks like a short "Name-shaped" line.
    for line in full_text.splitlines()[:6]:
        stripped = line.strip()
        if not stripped or EMAIL_RE.search(stripped) or PHONE_RE.search(stripped):
            continue
        words = stripped.split()
        if 1 <= len(words) <= 5 and all(w[0].isupper() or not w[0].isalpha() for w in words if w):
            return stripped
    return None


def _extract_years_of_experience(experience_text: str, experience_entries: list[ExperienceEntry]) -> float:
    # Only inspect the summary and employment history supplied by the caller.
    # Scanning the entire resume can mistake phrases in education (for example,
    # "four-year degree") for a candidate's professional experience.
    match = YEARS_EXPERIENCE_RE.search(experience_text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    durations = [e.duration_years for e in experience_entries if e.duration_years]
    if durations:
        return round(sum(durations), 1)
    # A resume with no employment entries has no supported professional
    # experience. Keep this distinct from years spent in education/projects.
    return 0.0


def _parse_duration(start: str, end: str) -> float | None:
    import datetime

    def _parse_year(token: str) -> int | None:
        token = token.strip().lower()
        if token in ("present", "current"):
            return datetime.date.today().year
        m = re.search(r"\d{4}", token)
        return int(m.group()) if m else None

    start_year = _parse_year(start)
    end_year = _parse_year(end)
    if start_year and end_year and end_year >= start_year:
        return float(end_year - start_year) or 0.5
    return None


def _extract_experience(sections: dict[str, list[str]]) -> list[ExperienceEntry]:
    entries: list[ExperienceEntry] = []
    for paragraph in sections.get("experience", []):
        date_match = DATE_RANGE_RE.search(paragraph)
        start, end, duration = None, None, None
        if date_match:
            start, end = date_match.group("start"), date_match.group("end")
            duration = _parse_duration(start, end)

        lines = [l.strip() for l in paragraph.splitlines() if l.strip()]
        header_line = lines[0] if lines else paragraph[:120]
        title, company = None, None
        if "," in header_line:
            parts = [p.strip() for p in header_line.split(",", 1)]
            title, company = parts[0], parts[1] if len(parts) > 1 else None
        elif " at " in header_line.lower():
            idx = header_line.lower().index(" at ")
            title, company = header_line[:idx].strip(), header_line[idx + 4 :].strip()
        else:
            title = header_line

        entries.append(
            ExperienceEntry(
                company=company,
                title=title,
                start_date=start,
                end_date=end,
                duration_years=duration,
                responsibilities_text=paragraph,
                evidence_text=paragraph[:500],
            )
        )
    return entries


def _extract_projects(sections: dict[str, list[str]]) -> list[ProjectEntry]:
    entries: list[ProjectEntry] = []
    for paragraph in sections.get("projects", []):
        lines = [l.strip() for l in paragraph.splitlines() if l.strip()]
        name = lines[0][:150] if lines else None
        techs = [skill for skill in TECHNICAL_SKILLS if re.search(r"(?<![a-zA-Z0-9])" + re.escape(skill) + r"(?![a-zA-Z0-9])", paragraph, re.IGNORECASE)]
        entries.append(
            ProjectEntry(name=name, description=paragraph, technologies=sorted(set(techs)), evidence_text=paragraph[:500])
        )
    return entries


def _extract_education(sections: dict[str, list[str]]) -> list[EducationEntry]:
    entries: list[EducationEntry] = []
    for paragraph in sections.get("education", []):
        degree = next((d for d in DEGREE_KEYWORDS if d in paragraph.lower()), None)
        year_match = re.search(r"\b(19|20)\d{2}\b", paragraph)
        lines = [l.strip() for l in paragraph.splitlines() if l.strip()]
        institution = None
        for line in lines:
            if degree and degree in line.lower():
                continue
            if len(line.split()) <= 8:
                institution = line
                break
        entries.append(
            EducationEntry(
                degree=degree,
                institution=institution,
                field_of_study=None,
                end_year=year_match.group() if year_match else None,
                evidence_text=paragraph[:400],
            )
        )
    return entries


def _extract_certifications(full_text: str, sections: dict[str, list[str]]) -> list[CertificationEntry]:
    entries: list[CertificationEntry] = []
    seen = set()
    search_space = "\n".join(sections.get("certifications", [])) or full_text
    for cert in CERTIFICATION_KEYWORDS:
        for sentence in _find_sentences_with_term(search_space, cert):
            if cert not in seen:
                entries.append(CertificationEntry(name=cert, evidence_text=sentence))
                seen.add(cert)
    return entries


def extract_structured_candidate(full_text: str) -> StructuredCandidate:
    sections = split_into_sections(full_text)
    candidate = StructuredCandidate()
    evidence: list[Evidence] = []

    candidate.full_name = _extract_name(full_text)
    email_match = EMAIL_RE.search(full_text)
    candidate.email = email_match.group() if email_match else None
    phone_match = PHONE_RE.search(full_text)
    candidate.phone = phone_match.group().strip() if phone_match else None

    if sections.get("summary"):
        candidate.summary = sections["summary"][0][:1000]

    # Skills: search the WHOLE document (not just the Skills section) so a
    # technology only mentioned inside a project/experience bullet is still
    # captured, each with a real evidence sentence.
    for skill in TECHNICAL_SKILLS:
        sentences = _find_sentences_with_term(full_text, skill)
        if sentences:
            candidate.technical_skills.append(skill)
            evidence.append(Evidence("skill", skill, sentences[0], section="technical_skills"))

    for skill in SOFT_SKILLS:
        sentences = _find_sentences_with_term(full_text, skill)
        if sentences:
            candidate.soft_skills.append(skill)
            evidence.append(Evidence("skill", skill, sentences[0], section="soft_skills"))

    candidate.experience = _extract_experience(sections)
    for exp in candidate.experience:
        if exp.title:
            candidate.job_titles.append(exp.title)
        evidence.append(Evidence("experience", exp.title or "experience entry", exp.evidence_text, section="experience"))

    candidate.projects = _extract_projects(sections)
    for proj in candidate.projects:
        evidence.append(Evidence("project", proj.name or "project entry", proj.evidence_text, section="projects"))

    candidate.education = _extract_education(sections)
    for edu in candidate.education:
        evidence.append(Evidence("education", edu.degree or "education entry", edu.evidence_text, section="education"))

    candidate.certifications = _extract_certifications(full_text, sections)
    for cert in candidate.certifications:
        evidence.append(Evidence("certification", cert.name, cert.evidence_text, section="certifications"))

    experience_text = "\n".join(sections.get("summary", []) + sections.get("experience", []))
    candidate.years_of_experience = _extract_years_of_experience(experience_text, candidate.experience)
    candidate.evidence = evidence
    return candidate
