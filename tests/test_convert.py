"""Tests for pdf2md.convert."""

from pathlib import Path

from pdf2md.convert import BatchSummary, ConversionResult, ConversionStatus, convert_one

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_conversion_result_fields():
    r = ConversionResult(
        source=Path("foo.pdf"),
        output_md=Path("outputs/foo/foo.md"),
        status=ConversionStatus.SUCCESS,
        n_pages=10,
        elapsed_s=1.5,
        error=None,
    )
    assert r.source == Path("foo.pdf")
    assert r.status == ConversionStatus.SUCCESS
    assert r.error is None


def test_batch_summary_fields():
    s = BatchSummary(succeeded=5, failed=1, skipped=2, elapsed_s=10.0, results=[])
    assert s.succeeded == 5
    assert s.total == 8


def test_convert_one_writes_markdown(tmp_path):
    result = convert_one(FIXTURE, tmp_path)

    assert result.status == ConversionStatus.SUCCESS
    assert result.error is None
    assert result.n_pages == 2
    assert result.elapsed_s > 0

    expected_md = tmp_path / "sample" / "sample.md"
    assert result.output_md == expected_md
    assert expected_md.exists()
    assert expected_md.stat().st_size > 0


def test_convert_one_creates_per_pdf_subfolder(tmp_path):
    convert_one(FIXTURE, tmp_path)
    assert (tmp_path / "sample").is_dir()
    assert (tmp_path / "sample" / "sample.md").is_file()
