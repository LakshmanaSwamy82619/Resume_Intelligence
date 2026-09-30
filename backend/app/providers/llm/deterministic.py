"""
Deterministic explanation generator.

This is the bottom rung of the LLM fallback chain (Section 12/13/33): it
never calls a network, never fails, and never fabricates anything. It
turns already-computed, evidence-backed structured facts (matched/partial/
missing requirements, evidence snippets) into readable prose using plain
string templates. It is intentionally less fluent than an LLM explanation
-- that is the honest trade for 100% availability.
"""
from __future__ import annotations

from app.providers.llm.base import LLMResult


def build_deterministic_explanation(
    candidate_name: str,
    matched: list[dict],
    partial: list[dict],
    missing: list[dict],
    years_of_experience: float | None,
    top_evidence: list[dict],
    fallback_reason: str = "Generated from structured resume evidence only.",
) -> LLMResult:
    lines: list[str] = []

    if years_of_experience is not None:
        lines.append(f"{candidate_name} has approximately {years_of_experience:.1f} years of relevant experience.")

    if matched:
        matched_values = ", ".join(m["requirement"] for m in matched[:8])
        lines.append(f"Matched requirements: {matched_values}.")

    if partial:
        partial_values = ", ".join(p["requirement"] for p in partial[:8])
        lines.append(f"Partially matched requirements (evidence is limited or indirect): {partial_values}.")

    if missing:
        missing_values = ", ".join(m["requirement"] for m in missing[:8])
        lines.append(f"No resume evidence was found for: {missing_values}.")

    if top_evidence:
        lines.append("Supporting evidence from the resume:")
        for ev in top_evidence[:3]:
            snippet = ev.get("evidence_text", "").strip()
            if len(snippet) > 220:
                snippet = snippet[:217] + "..."
            lines.append(f'- "{snippet}" (source: {ev.get("source_file", "resume")}, page {ev.get("page_number", "n/a")})')

    if not top_evidence:
        lines.append("No resume evidence was extracted to support a qualification match for this search.")

    if not lines:
        lines.append(f"{candidate_name} was retrieved for this search but no structured evidence could be extracted.")

    text = "\n".join(lines)

    return LLMResult(
        text=text,
        provider="deterministic",
        model_used=None,
        fallback_used=True,
        fallback_reason=fallback_reason,
    )
