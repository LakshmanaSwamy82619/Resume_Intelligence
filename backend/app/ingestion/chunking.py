"""
Section-aware chunking (Section 6/9).

Resumes are chunked by detected section (skills / experience / projects /
education / certifications / summary / other) rather than fixed-size
sliding windows, because retrieval quality benefits from knowing *which*
part of the resume a matching chunk came from (e.g. "Python" appearing in
the Skills section is stronger evidence than "Python" appearing once in a
Certifications section). Within an oversized section we still sub-chunk by
paragraph/blank-line boundaries and cap chunk length so embeddings stay
meaningful (very long chunks dilute embedding quality).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SECTION_HEADERS: dict[str, list[str]] = {
    "summary": ["summary", "profile", "profile summary", "objective", "about me"],
    "skills": ["skills", "technical skills", "technical skills and interests", "core competencies", "technologies", "tech stack"],
    "experience": ["experience", "work experience", "professional experience", "employment history", "career history"],
    "projects": ["projects", "project experience", "personal projects", "academic projects", "key projects"],
    "education": ["education", "academic background", "qualifications"],
    "certifications": ["certifications", "certificates", "licenses", "credentials"],
    "achievements": ["achievements", "awards", "honors"],
    "languages": ["languages"],
}

_HEADER_LOOKUP = {alias: section for section, aliases in SECTION_HEADERS.items() for alias in aliases}

_MAX_CHUNK_CHARS = 900


@dataclass
class Chunk:
    section: str
    text: str
    page_number: int | None


def _looks_like_header(line: str) -> str | None:
    stripped = re.sub(r"[\s:|•·-]+$", "", line.strip()).lower()
    if not stripped or len(stripped) > 40:
        return None
    if stripped in _HEADER_LOOKUP:
        return _HEADER_LOOKUP[stripped]
    # Do not fuzzy-match section names inside ordinary prose. For example,
    # "project experience." can be a wrapped summary sentence, not a header;
    # treating it as one can place an education date range in employment.
    return None


def split_into_sections(full_text: str) -> dict[str, list[str]]:
    """Return {section_name: [paragraph, ...]}. Unrecognized content before
    the first header (or when no headers are found at all) goes to
    'summary'/'other'.
    """
    lines = full_text.splitlines()
    sections: dict[str, list[str]] = {}
    current_section = "summary"
    buffer: list[str] = []

    def _flush():
        nonlocal buffer
        if buffer:
            text = "\n".join(buffer).strip()
            if text:
                sections.setdefault(current_section, []).append(text)
            buffer = []

    for line in lines:
        header = _looks_like_header(line)
        if header:
            _flush()
            current_section = header
            continue
        if line.strip() == "":
            _flush()
            continue
        buffer.append(line)
    _flush()

    if not sections:
        sections["other"] = [full_text]

    return sections


def _sub_chunk(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    # Split on sentence-ish boundaries and re-pack greedily.
    parts = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = part
        else:
            current = f"{current} {part}".strip()
    if current:
        chunks.append(current.strip())
    return chunks


def build_chunks(full_text: str, page_lookup: dict[str, int] | None = None) -> list[Chunk]:
    sections = split_into_sections(full_text)
    chunks: list[Chunk] = []
    for section, paragraphs in sections.items():
        for paragraph in paragraphs:
            for sub in _sub_chunk(paragraph):
                if sub.strip():
                    chunks.append(Chunk(section=section, text=sub.strip(), page_number=None))
    return chunks
