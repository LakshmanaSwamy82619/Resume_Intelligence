from app.ingestion.chunking import build_chunks, split_into_sections
from app.ingestion.dedup import compute_candidate_fingerprint, compute_content_hash, compute_file_hash
from app.ingestion.structuring import extract_structured_candidate

SAMPLE_RESUME = """Alice Johnson
alice.johnson@example.com
+1-555-0100

Summary
Data scientist with a strong background in machine learning and backend engineering.

Skills
Python, SQL, Machine Learning, NLP, PyTorch, Pandas, AWS, Docker

Experience
Machine Learning Engineer, Acme Analytics
Jan 2021 - Present
Built and deployed NLP models for customer support ticket classification using Python and PyTorch.

Education
B.Tech Computer Science, State University, 2019

Certifications
AWS Certified Machine Learning
"""


def test_split_into_sections_finds_known_headers():
    sections = split_into_sections(SAMPLE_RESUME)
    assert "skills" in sections
    assert "experience" in sections
    assert "education" in sections
    assert "certifications" in sections


def test_build_chunks_produces_nonempty_chunks_with_sections():
    chunks = build_chunks(SAMPLE_RESUME)
    assert len(chunks) > 0
    sections_seen = {c.section for c in chunks}
    assert "skills" in sections_seen


def test_extract_structured_candidate_finds_contact_info():
    candidate = extract_structured_candidate(SAMPLE_RESUME)
    assert candidate.email == "alice.johnson@example.com"
    assert candidate.full_name == "Alice Johnson"


def test_extract_structured_candidate_finds_skills_with_evidence():
    candidate = extract_structured_candidate(SAMPLE_RESUME)
    assert "python" in candidate.technical_skills
    assert "machine learning" in candidate.technical_skills
    skill_evidence = [e for e in candidate.evidence if e.field_type == "skill" and e.field_value == "python"]
    assert skill_evidence, "Every extracted skill must carry an evidence sentence"
    assert "python" in skill_evidence[0].evidence_text.lower()


def test_extract_structured_candidate_never_fabricates_missing_skill():
    candidate = extract_structured_candidate(SAMPLE_RESUME)
    assert "kubernetes" not in candidate.technical_skills  # never mentioned in the resume


def test_extract_structured_candidate_finds_certifications_and_education():
    candidate = extract_structured_candidate(SAMPLE_RESUME)
    assert any(c.name == "aws certified" for c in candidate.certifications)
    assert any(e.degree and "b.tech" in e.degree for e in candidate.education)


def test_dedup_hashes_are_deterministic():
    content = b"some resume bytes"
    assert compute_file_hash(content) == compute_file_hash(content)
    assert compute_content_hash("normalized text") == compute_content_hash("normalized text")


def test_candidate_fingerprint_prefers_email():
    fp1 = compute_candidate_fingerprint("a@example.com", "555-1234", "A B")
    fp2 = compute_candidate_fingerprint("a@example.com", "555-9999", "Different Name")
    assert fp1 == fp2  # same email -> same fingerprint regardless of other fields


def test_candidate_fingerprint_none_when_no_identity_fields():
    assert compute_candidate_fingerprint(None, None, None) is None
