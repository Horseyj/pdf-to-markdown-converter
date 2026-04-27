"""Tests for pdf2md.convert."""

import importlib.metadata
import shutil
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


def test_convert_one_writes_provenance_header(tmp_path):
    convert_one(FIXTURE, tmp_path)
    text = (tmp_path / "sample" / "sample.md").read_text()
    docling_version = importlib.metadata.version("docling")

    assert text.startswith("<!-- source: sample.pdf -->\n")
    assert "<!-- pages: 2 -->\n" in text.splitlines()[1] + "\n"
    assert f"<!-- extractor: docling {docling_version} -->\n" in text.splitlines()[2] + "\n"


def test_convert_one_output_is_deterministic(tmp_path):
    convert_one(FIXTURE, tmp_path / "a")
    convert_one(FIXTURE, tmp_path / "b")
    a = (tmp_path / "a" / "sample" / "sample.md").read_bytes()
    b = (tmp_path / "b" / "sample" / "sample.md").read_bytes()
    assert a == b


def test_convert_one_with_images_does_not_error(tmp_path):
    """The fixture has no images, but the with_images=True path must not error."""
    result = convert_one(FIXTURE, tmp_path, with_images=True)
    assert result.status == ConversionStatus.SUCCESS


def test_convert_one_no_images_suppresses_sidecar(tmp_path):
    convert_one(FIXTURE, tmp_path, with_images=False)
    out_dir = tmp_path / "sample"
    artifacts = out_dir / "sample_artifacts"
    # Either the artifacts folder doesn't exist, or it's empty.
    if artifacts.exists():
        assert not any(artifacts.iterdir()), f"expected no images, found {list(artifacts.iterdir())}"


def test_convert_batch_happy_path(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    # Two copies of the fixture under different names.
    shutil.copy(FIXTURE, in_dir / "doc-a.pdf")
    shutil.copy(FIXTURE, in_dir / "doc-b.pdf")

    from pdf2md.convert import convert_batch

    summary = convert_batch(in_dir, out_dir)

    assert summary.total == 2
    assert summary.succeeded == 2
    assert summary.failed == 0
    assert summary.skipped == 0
    assert (out_dir / "doc-a" / "doc-a.md").is_file()
    assert (out_dir / "doc-b" / "doc-b.md").is_file()


def test_convert_batch_non_recursive(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    sub = in_dir / "subfolder"
    sub.mkdir(parents=True)
    shutil.copy(FIXTURE, in_dir / "top.pdf")
    shutil.copy(FIXTURE, sub / "nested.pdf")

    from pdf2md.convert import convert_batch

    summary = convert_batch(in_dir, out_dir)

    assert summary.total == 1
    assert (out_dir / "top" / "top.md").is_file()
    assert not (out_dir / "nested").exists()


def test_convert_batch_skips_existing(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    shutil.copy(FIXTURE, in_dir / "doc.pdf")

    from pdf2md.convert import convert_batch

    first = convert_batch(in_dir, out_dir)
    assert first.succeeded == 1 and first.skipped == 0

    second = convert_batch(in_dir, out_dir)
    assert second.succeeded == 0 and second.skipped == 1
    assert second.results[0].status == ConversionStatus.SKIPPED
    assert second.results[0].error is None


def test_convert_batch_force_overrides_skip(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    shutil.copy(FIXTURE, in_dir / "doc.pdf")

    from pdf2md.convert import convert_batch

    convert_batch(in_dir, out_dir)
    second = convert_batch(in_dir, out_dir, force=True)
    assert second.succeeded == 1 and second.skipped == 0
