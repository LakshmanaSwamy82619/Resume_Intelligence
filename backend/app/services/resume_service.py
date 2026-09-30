from __future__ import annotations

import os
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import UnsupportedFileError, ValidationAppError
from app.ingestion.chunking import build_chunks
from app.ingestion.dedup import compute_candidate_fingerprint, compute_content_hash, compute_file_hash, normalize_text_for_hash
from app.ingestion.parsers import SUPPORTED_MIME_TYPES, parse_document
from app.ingestion.structuring import extract_structured_candidate
from app.models.candidate import (
    Candidate,
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateProject,
    Resume,
    ResumeChunk,
    ResumeEvidence,
)
from app.models.enums import ProcessingStatus
from app.providers.embeddings.chain import EmbeddingProviderChain, get_embedding_provider_chain

settings = get_settings()


def _prefer_full_name_from_filename(full_name: str | None, original_filename: str) -> str | None:
    """Use a clearly fuller resume filename name when the extracted name uses an initial."""
    if not full_name:
        return full_name
    extracted_parts = full_name.split()
    if not any(len(part.rstrip(".")) == 1 for part in extracted_parts):
        return full_name

    stem = os.path.splitext(os.path.basename(original_filename))[0]
    name_part = re.split(r"[_-]", stem, maxsplit=1)[0]
    filename_parts = re.findall(r"[A-Za-z]+", name_part)
    normalized_filename = " ".join(filename_parts)
    extracted_words = {part.casefold().strip(".") for part in extracted_parts if len(part.strip(".")) > 1}
    filename_words = {part.casefold() for part in filename_parts}
    if len(filename_parts) >= 2 and extracted_words.intersection(filename_words):
        return normalized_filename
    return full_name


def validate_upload(filename: str, mime_type: str, file_size_bytes: int) -> None:
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise UnsupportedFileError(f"Unsupported file type '{mime_type}'. Allowed: PDF, DOCX, TXT.")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise ValidationAppError(f"File exceeds the {settings.MAX_UPLOAD_MB}MB upload limit.")
    if file_size_bytes == 0:
        raise ValidationAppError("Uploaded file is empty.")


async def read_upload_limited(upload, max_bytes: int) -> bytes:
    """Read an UploadFile incrementally and stop once it exceeds max_bytes."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(min(64 * 1024, max_bytes + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValidationAppError(f"Uploaded file exceeds the {max_bytes} byte upload limit.")
        chunks.append(chunk)
    return b"".join(chunks)


def safe_storage_filename(original_filename: str) -> str:
    """Prevents path traversal / unsafe filenames (Section 29) by generating
    a random name and keeping only a sanitized extension from the original.
    """
    ext = os.path.splitext(original_filename)[1].lower()
    ext = "".join(c for c in ext if c.isalnum() or c == ".")[:10]
    return f"{uuid.uuid4().hex}{ext}"


async def find_duplicate_resume(db: AsyncSession, file_hash: str, content_hash: str | None) -> Resume | None:
    stmt = select(Resume).where(Resume.file_hash == file_hash)
    result = await db.execute(stmt)
    existing = result.scalars().first()
    return existing


async def find_candidate_by_fingerprint(db: AsyncSession, fingerprint: str | None) -> Candidate | None:
    if not fingerprint:
        return None
    stmt = select(Candidate).where(Candidate.fingerprint == fingerprint)
    result = await db.execute(stmt)
    return result.scalars().first()


async def ingest_resume_file(
    db: AsyncSession,
    file_bytes: bytes,
    original_filename: str,
    mime_type: str,
    uploaded_by_user_id: str | None,
    embedding_chain: EmbeddingProviderChain | None = None,
    source_relative_path: str | None = None,
    source_category: str | None = None,
) -> tuple[Resume, bool]:
    """Full single-resume ingestion: validate -> dedup check -> parse ->
    structure -> persist candidate/resume/evidence -> chunk+embed.
    Returns (resume, is_duplicate).
    """
    validate_upload(original_filename, mime_type, len(file_bytes))
    embedding_chain = embedding_chain or get_embedding_provider_chain()

    file_hash = compute_file_hash(file_bytes)
    existing_resume = await find_duplicate_resume(db, file_hash, None)
    if existing_resume:
        return existing_resume, True

    parsed = parse_document(file_bytes, mime_type, original_filename)
    structured = extract_structured_candidate(parsed.full_text)
    structured.full_name = _prefer_full_name_from_filename(structured.full_name, original_filename)

    fingerprint = compute_candidate_fingerprint(structured.email, structured.phone, structured.full_name)
    candidate = await find_candidate_by_fingerprint(db, fingerprint) if fingerprint else None
    is_new_candidate = candidate is None
    if candidate is None:
        candidate = Candidate(fingerprint=fingerprint)
        db.add(candidate)
        await db.flush()

    # Refresh structured fields on the candidate with the latest resume's data.
    candidate.full_name = structured.full_name or candidate.full_name
    candidate.email = structured.email or candidate.email
    candidate.phone = structured.phone or candidate.phone
    candidate.summary = structured.summary or candidate.summary
    candidate.technical_skills = sorted(set(structured.technical_skills))
    candidate.soft_skills = sorted(set(structured.soft_skills))
    candidate.job_titles = list(dict.fromkeys(structured.job_titles))
    candidate.years_of_experience = structured.years_of_experience

    storage_dir = settings.UPLOAD_DIR
    os.makedirs(storage_dir, exist_ok=True)
    stored_name = safe_storage_filename(original_filename)
    storage_path = os.path.join(storage_dir, stored_name)
    with open(storage_path, "wb") as f:
        f.write(file_bytes)

    resume = Resume(
        candidate_id=candidate.id,
        uploaded_by_user_id=uploaded_by_user_id,
        original_filename=original_filename,
        source_relative_path=source_relative_path,
        source_category=source_category,
        storage_path=storage_path,
        mime_type=mime_type,
        file_size_bytes=len(file_bytes),
        file_hash=file_hash,
        raw_text=parsed.full_text,
        page_count=parsed.page_count,
        extraction_method=parsed.extraction_method,
        used_ocr=parsed.used_ocr,
        processing_status=ProcessingStatus.PROCESSING.value,
    )
    db.add(resume)
    await db.flush()

    # Persist evidence rows first so structured entities can reference them.
    evidence_id_by_value: dict[tuple[str, str], str] = {}
    for ev in structured.evidence:
        evidence_text = ev.evidence_text
        evidence_folded = evidence_text.casefold()
        source_page = next(
            (page.page_number for page in parsed.pages if evidence_folded and evidence_folded in page.text.casefold()),
            None,
        )
        record = ResumeEvidence(
            resume_id=resume.id,
            candidate_id=candidate.id,
            field_type=ev.field_type,
            field_value=ev.field_value,
            evidence_text=evidence_text,
            page_number=source_page,
            confidence=1.0,
        )
        db.add(record)
        await db.flush()
        evidence_id_by_value[(ev.field_type, ev.field_value.lower())] = record.id

    for exp in structured.experience:
        db.add(
            CandidateExperience(
                candidate_id=candidate.id,
                company=exp.company,
                title=exp.title,
                start_date=exp.start_date,
                end_date=exp.end_date,
                duration_years=exp.duration_years,
                responsibilities_text=exp.responsibilities_text,
                evidence_id=evidence_id_by_value.get(("experience", (exp.title or "experience entry").lower())),
            )
        )
    for proj in structured.projects:
        db.add(
            CandidateProject(
                candidate_id=candidate.id,
                name=proj.name,
                description=proj.description,
                technologies=proj.technologies,
                evidence_id=evidence_id_by_value.get(("project", (proj.name or "project entry").lower())),
            )
        )
    for edu in structured.education:
        db.add(
            CandidateEducation(
                candidate_id=candidate.id,
                degree=edu.degree,
                institution=edu.institution,
                field_of_study=edu.field_of_study,
                end_year=edu.end_year,
                evidence_id=evidence_id_by_value.get(("education", (edu.degree or "education entry").lower())),
            )
        )
    for cert in structured.certifications:
        db.add(
            CandidateCertification(
                candidate_id=candidate.id,
                name=cert.name,
                evidence_id=evidence_id_by_value.get(("certification", cert.name.lower())),
            )
        )

    # Chunk + embed.
    chunks = build_chunks(parsed.full_text)
    if chunks:
        texts = [c.text for c in chunks]
        try:
            vectors = await embedding_chain.embed_texts(texts)
        except Exception:
            vectors = None

        for i, chunk in enumerate(chunks):
            db.add(
                ResumeChunk(
                    resume_id=resume.id,
                    candidate_id=candidate.id,
                    chunk_index=i,
                    section=chunk.section,
                    text=chunk.text,
                    embedding=vectors[i].tolist() if vectors is not None else None,
                    embedding_model=embedding_chain.last_provider_used if vectors is not None else None,
                )
            )

    resume.processing_status = ProcessingStatus.COMPLETED.value
    await db.commit()
    await db.refresh(resume)
    return resume, False
