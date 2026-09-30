"""
Job description / natural-language hiring-requirement understanding
(Section 8).

Accepts any of: uploaded JD text, pasted JD text, a natural-language
recruiter query ("Find candidates with Python and SQL, at least 3 years of
experience..."), or a partially structured request. All are just "raw_text"
by the time they reach this module -- the API layer (Section 8 A-D)
distinguishes *how* the text arrived, not how it's parsed.

Rule-based baseline (always runs, never fails):
  - Skill/technology requirements via the same taxonomy used for resumes,
    so a requirement and a resume skill are the same canonical string and
    can be compared exactly downstream.
  - MANDATORY vs PREFERRED split via explicit cue phrases ("must have",
    "required", "mandatory" vs "nice to have", "preferred", "a plus",
    "bonus"). Requirements outside any cued sentence default to PREFERRED
    for a full JD (safer default: don't silently disqualify candidates on
    an ambiguous requirement) and MANDATORY for a short natural-language
    query (a recruiter typing "Python and SQL, 3+ years" means it).
  - Minimum years of experience via regex.
  - Education / certification requirement keywords via the resume
    taxonomy's own keyword lists (shared vocabulary = comparable facts).

Optional LLM enrichment (Section 8, best-effort, Section 12 fallback
applies): if an LLM provider is available, we ask it only to (a) refine
the mandatory/preferred split for skills the rule-based pass already found,
and (b) extract a short job title / domain label -- we deliberately do NOT
let the LLM invent new required skills that don't appear in the raw text,
so a provider outage or a bad LLM response can never change *what* is
required, only how it's labelled/titled. If the LLM call fails for any
reason, the rule-based result is returned unchanged.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.ingestion.skills_taxonomy import CERTIFICATION_KEYWORDS, DEGREE_KEYWORDS, TECHNICAL_SKILLS
from app.models.enums import RequirementPriority
from app.providers.llm.chain import LLMProviderChain

MANDATORY_CUES = re.compile(
    r"\b(must have|must-have|required|requires|requirement|mandatory|need to have|should have)\b", re.IGNORECASE
)
PREFERRED_CUES = re.compile(
    r"\b(nice to have|preferred|a plus|is a plus|bonus|good to have|desirable|advantageous)\b", re.IGNORECASE
)
MIN_YEARS_RE = re.compile(
    r"(?:at least|minimum of|min\.?|over)?\s*(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\b", re.IGNORECASE
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\n])\s+")


@dataclass
class Requirement:
    requirement_type: str  # skill/technology/education/certification/domain/responsibility
    value: str
    priority: str  # mandatory/preferred
    evidence_sentence: str


@dataclass
class ExtractedJobRequirements:
    title: str | None = None
    domain: str | None = None
    min_experience_years: float | None = None
    preferred_experience_years: float | None = None
    requirements: list[Requirement] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    llm_enrichment_used: bool = False
    llm_fallback_reason: str | None = None

    def mandatory(self) -> list[Requirement]:
        return [r for r in self.requirements if r.priority == RequirementPriority.MANDATORY.value]

    def preferred(self) -> list[Requirement]:
        return [r for r in self.requirements if r.priority == RequirementPriority.PREFERRED.value]


def _sentence_priority(sentence: str, default: str) -> str:
    if MANDATORY_CUES.search(sentence):
        return RequirementPriority.MANDATORY.value
    if PREFERRED_CUES.search(sentence):
        return RequirementPriority.PREFERRED.value
    return default


def _find_sentences_with_term(text: str, term: str) -> list[str]:
    sentences = SENTENCE_SPLIT_RE.split(text)
    pattern = re.compile(r"(?<![a-zA-Z0-9])" + re.escape(term) + r"(?![a-zA-Z0-9])", re.IGNORECASE)
    return [s.strip() for s in sentences if s.strip() and pattern.search(s)]


def extract_requirements_rule_based(raw_text: str, is_short_query: bool | None = None) -> ExtractedJobRequirements:
    if is_short_query is None:
        is_short_query = len(raw_text.split()) < 40

    default_priority = RequirementPriority.MANDATORY.value if is_short_query else RequirementPriority.PREFERRED.value

    result = ExtractedJobRequirements()

    for skill in TECHNICAL_SKILLS:
        sentences = _find_sentences_with_term(raw_text, skill)
        if sentences:
            priority = _sentence_priority(sentences[0], default_priority)
            result.requirements.append(Requirement("skill", skill, priority, sentences[0]))

    for degree in DEGREE_KEYWORDS:
        sentences = _find_sentences_with_term(raw_text, degree)
        if sentences:
            priority = _sentence_priority(sentences[0], RequirementPriority.PREFERRED.value)
            result.requirements.append(Requirement("education", degree, priority, sentences[0]))

    for cert in CERTIFICATION_KEYWORDS:
        sentences = _find_sentences_with_term(raw_text, cert)
        if sentences:
            priority = _sentence_priority(sentences[0], RequirementPriority.PREFERRED.value)
            result.requirements.append(Requirement("certification", cert, priority, sentences[0]))

    years_matches = MIN_YEARS_RE.findall(raw_text)
    if years_matches:
        try:
            years_values = sorted({float(y) for y in years_matches})
            result.min_experience_years = years_values[0]
            if len(years_values) > 1:
                result.preferred_experience_years = years_values[-1]
        except ValueError:
            pass

    # Responsibilities: bullet-like lines that aren't already captured as a
    # skill/requirement sentence.
    for line in raw_text.splitlines():
        stripped = line.strip().lstrip("-•*").strip()
        if 6 <= len(stripped.split()) <= 30 and stripped.endswith((".", "")):
            result.responsibilities.append(stripped)

    # Title: first non-empty line if it's short (JDs commonly lead with the title).
    first_line = next((l.strip() for l in raw_text.splitlines() if l.strip()), None)
    if first_line and len(first_line.split()) <= 8:
        result.title = first_line

    return result


async def extract_requirements(raw_text: str, llm_chain: LLMProviderChain | None, is_short_query: bool | None = None) -> ExtractedJobRequirements:
    result = extract_requirements_rule_based(raw_text, is_short_query=is_short_query)

    if llm_chain is None:
        return result

    system_prompt = (
        "You label job-requirement priority and identify the role title/domain. "
        "You must not invent requirements that are not already listed. "
        "Return strict JSON only: "
        '{"title": str|null, "domain": str|null, '
        '"mandatory_terms": [str,...], "preferred_terms": [str,...]}'
    )
    listed_terms = [r.value for r in result.requirements]
    user_prompt = (
        f"Job text:\n{raw_text[:3000]}\n\n"
        f"Already-detected terms (classify each into mandatory_terms or preferred_terms, "
        f"using only terms from this list): {listed_terms}"
    )

    try:
        llm_result = await llm_chain.complete(system_prompt, user_prompt, temperature=0.0, max_tokens=600)
        if llm_result.fallback_used or not llm_result.text:
            result.llm_fallback_reason = llm_result.fallback_reason
            return result

        parsed = json.loads(_strip_code_fences(llm_result.text))
        mandatory_set = {t.lower() for t in parsed.get("mandatory_terms", [])}
        preferred_set = {t.lower() for t in parsed.get("preferred_terms", [])}

        for req in result.requirements:
            if req.value.lower() in mandatory_set:
                req.priority = RequirementPriority.MANDATORY.value
            elif req.value.lower() in preferred_set:
                req.priority = RequirementPriority.PREFERRED.value

        if parsed.get("title"):
            result.title = parsed["title"]
        if parsed.get("domain"):
            result.domain = parsed["domain"]
        result.llm_enrichment_used = True
    except Exception as exc:
        # Never let LLM enrichment failure break JD understanding.
        result.llm_fallback_reason = f"llm_enrichment_failed: {exc}"

    return result


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"```$", "", text)
    return text.strip()
