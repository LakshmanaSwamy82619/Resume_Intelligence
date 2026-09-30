from __future__ import annotations

import textwrap


def _pdf_text(value: object) -> str:
    text = str(value or "").encode("latin-1", "replace").decode("latin-1")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def shortlist_pdf(query: str, candidates: list[tuple[object, object]]) -> bytes:
    """Create a dependency-free, printable PDF shortlist (one candidate/page)."""
    pages: list[list[str]] = []
    for search_candidate, candidate in candidates:
        lines = [
            "RESUME INTELLIGENCE - SHORTLIST",
            f"Search: {query}",
            f"Rank {search_candidate.rank} | {candidate.full_name if candidate else 'Candidate'} | Score {search_candidate.final_score:.3f}",
            f"Experience: {candidate.years_of_experience if candidate and candidate.years_of_experience is not None else 'Not provided'} years",
            "",
            "WHY THIS CANDIDATE",
            search_candidate.explanation_summary or "No explanation was recorded.",
        ]
        for heading, key in (("MATCHED", "matched_requirements"), ("PARTIAL", "partial_requirements"), ("MISSING", "missing_requirements")):
            lines.extend(["", heading])
            findings = getattr(search_candidate, key) or []
            lines.extend(["- " + str(item.get("requirement", "")) for item in findings] or ["- None recorded"])
        lines.extend(["", "SOURCE EVIDENCE"])
        evidence = search_candidate.evidence or []
        for item in evidence:
            source = item.get("source_file") or "Resume"
            page = f", page {item['page_number']}" if item.get("page_number") else ""
            lines.extend(textwrap.wrap(f"{item.get('evidence_text', '')} ({source}{page})", width=92) or [f"({source}{page})"])
        wrapped = [part for line in lines for part in (textwrap.wrap(line, width=92) or [""])]
        pages.append(wrapped[:48])

    objects: list[bytes] = [b""]
    def add(content: bytes) -> int:
        objects.append(content)
        return len(objects) - 1

    catalog_id = add(b"")
    pages_id = add(b"")
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    for lines in pages:
        commands = ["BT", "/F1 10 Tf", "48 748 Td", "14 TL"]
        for line in lines:
            commands.append(f"({_pdf_text(line)}) Tj T*")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", "replace")
        stream_id = add(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        page_ids.append(add(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {stream_id} 0 R >>".encode()))
    objects[catalog_id] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode()
    objects[pages_id] = f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(page_ids)} >>".encode()
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, content in enumerate(objects[1:], start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(content)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects)} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(output)
