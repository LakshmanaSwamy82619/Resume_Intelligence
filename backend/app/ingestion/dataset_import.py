"""Import local resume datasets through the normal resume ingestion pipeline.

Run from the backend directory with ``python -m app.ingestion.dataset_import``.
The importer never returns source paths through an API; the relative path is
kept only as internal provenance metadata.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import mimetypes
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.providers.embeddings.chain import EmbeddingProviderChain
from app.services.resume_service import ingest_resume_file, validate_upload

logger = logging.getLogger("app.ingestion.dataset_import")
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}


def discover_resumes(data_dir: Path) -> list[Path]:
    """Return supported files recursively, excluding app-owned upload fixtures."""
    if not data_dir.exists():
        raise FileNotFoundError(f"Dataset directory does not exist: {data_dir}")
    root = data_dir.resolve()
    return sorted(
        path
        for path in data_dir.rglob("*")
        if path.is_file()
        and path.resolve().is_relative_to(root)
        and path.suffix.lower() in SUPPORTED_SUFFIXES
        and "test_uploads" not in path.relative_to(data_dir).parts
        and "uploads" not in path.relative_to(data_dir).parts
    )


def _metadata(path: Path, data_dir: Path) -> tuple[str, str | None]:
    relative = path.relative_to(data_dir).as_posix()
    category = path.parent.name if path.parent != data_dir else None
    return relative, category


async def import_dataset(
    db: AsyncSession,
    data_dir: Path,
    limit: int | None = None,
    embedding_chain: EmbeddingProviderChain | None = None,
) -> dict:
    files = discover_resumes(data_dir)
    if limit is not None:
        files = files[:limit]

    summary = {"discovered": len(files), "imported": 0, "duplicates": 0, "failed": 0, "errors": []}
    for path in files:
        relative, category = _metadata(path, data_dir)
        try:
            mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            validate_upload(path.name, mime_type, path.stat().st_size)
            content = path.read_bytes()
            _, duplicate = await ingest_resume_file(
                db,
                file_bytes=content,
                original_filename=path.name,
                mime_type=mime_type,
                uploaded_by_user_id=None,
                embedding_chain=embedding_chain,
                source_relative_path=relative,
                source_category=category,
            )
            summary["duplicates" if duplicate else "imported"] += 1
        except Exception as exc:
            await db.rollback()
            summary["failed"] += 1
            summary["errors"].append({"source": relative, "error": str(exc)[:500]})
            logger.warning("dataset_resume_failed", extra={"extra_fields": {"source": relative, "error": str(exc)}})
    return summary


async def _run(args: argparse.Namespace) -> dict:
    async with AsyncSessionLocal() as db:
        return await import_dataset(db, args.data_dir.resolve(), args.limit)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import local resumes through the Resume Intelligence pipeline.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Dataset root (default: ./data)")
    parser.add_argument("--limit", type=int, default=None, help="Process at most this many resumes")
    parser.add_argument("--report", type=Path, default=None, help="Optional JSON report output path")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    summary = asyncio.run(_run(args))
    rendered = json.dumps(summary, indent=2)
    print(rendered)
    if args.report:
        args.report.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
