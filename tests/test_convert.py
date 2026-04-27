"""Tests for pdf2md.convert."""

from pathlib import Path

from pdf2md.convert import ConversionResult, BatchSummary, ConversionStatus


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
