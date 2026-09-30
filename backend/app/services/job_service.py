from __future__ import annotations

from app.ingestion.jd_extraction import ExtractedJobRequirements, extract_requirements
from app.models.enums import RequirementPriority
from app.models.job import JobDescription, JobRequirement
from app.providers.llm.chain import LLMProviderChain
from sqlalchemy.ext.asyncio import AsyncSession


async def create_job_description(
    db: AsyncSession, created_by_user_id: str, raw_text: str, title: str | None, input_mode: str, llm_chain: LLMProviderChain | None,
    source_filename: str | None = None,
) -> JobDescription:
    extracted: ExtractedJobRequirements = await extract_requirements(
        raw_text, llm_chain, is_short_query=(input_mode == "natural_language")
    )

    job = JobDescription(
        created_by_user_id=created_by_user_id,
        title=title or extracted.title,
        raw_text=raw_text,
        input_mode=input_mode,
        source_filename=source_filename,
        llm_enrichment_used=extracted.llm_enrichment_used,
        extracted_domain=extracted.domain,
        extracted_responsibilities=extracted.responsibilities,
        min_experience_years=extracted.min_experience_years,
        preferred_experience_years=extracted.preferred_experience_years,
    )
    db.add(job)
    await db.flush()

    for req in extracted.requirements:
        db.add(
            JobRequirement(
                job_description_id=job.id,
                requirement_type=req.requirement_type,
                value=req.value,
                priority=req.priority,
            )
        )

    await db.commit()
    await db.refresh(job)
    return job


def split_requirements(job: JobDescription) -> tuple[list[JobRequirement], list[JobRequirement]]:
    mandatory = [r for r in job.requirements if r.priority == RequirementPriority.MANDATORY.value]
    preferred = [r for r in job.requirements if r.priority == RequirementPriority.PREFERRED.value]
    return mandatory, preferred
