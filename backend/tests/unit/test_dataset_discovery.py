from app.ingestion.dataset_import import _metadata, discover_resumes


def test_discovery_recurses_and_skips_application_upload_storage(tmp_path):
    data_dir = tmp_path / "data"
    (data_dir / "ACCOUNTANT").mkdir(parents=True)
    (data_dir / "nested" / "ENGINEERING").mkdir(parents=True)
    (data_dir / "test_uploads").mkdir()
    (data_dir / "ACCOUNTANT" / "one.PDF").write_bytes(b"pdf")
    (data_dir / "nested" / "ENGINEERING" / "two.docx").write_bytes(b"docx")
    (data_dir / "test_uploads" / "fixture.txt").write_text("fixture")
    (data_dir / "Resume.csv").write_text("ID,Category")

    found = discover_resumes(data_dir)

    assert [path.name for path in found] == ["one.PDF", "two.docx"]
    assert _metadata(found[0], data_dir) == ("ACCOUNTANT/one.PDF", "ACCOUNTANT")
    assert _metadata(found[1], data_dir) == ("nested/ENGINEERING/two.docx", "ENGINEERING")
