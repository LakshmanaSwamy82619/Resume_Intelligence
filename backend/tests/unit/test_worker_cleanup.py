from __future__ import annotations

from app.workers.tasks import _cleanup_bulk_files


def test_bulk_temp_cleanup_removes_files_and_job_directory(tmp_path):
    job_dir = tmp_path / "bulk-job"
    job_dir.mkdir()
    first = job_dir / "one.txt"
    second = job_dir / "two.txt"
    first.write_text("one")
    second.write_text("two")

    _cleanup_bulk_files([str(first), str(second)])

    assert not job_dir.exists()
