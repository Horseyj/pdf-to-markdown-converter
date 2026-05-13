"""Tests for pdf2md.convert."""

import importlib.metadata
import re
import shutil
from pathlib import Path

from pdf2md.convert import (
    BatchSummary,
    ConversionResult,
    ConversionStatus,
    _prune_repeated_images,
    convert_one,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"
FIXTURE_WITH_IMAGE = Path(__file__).parent / "fixtures" / "sample_with_image.pdf"


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


def test_convert_one_runs_postprocess(tmp_path):
    """Regression: HTML entities must be decoded in the produced .md, proving
    the postprocess pass was wired into convert_one (not just left as a library
    function)."""
    convert_one(FIXTURE, tmp_path)
    text = (tmp_path / "sample" / "sample.md").read_text()
    # The sample PDF text contains ampersands; docling emits them as &amp;.
    # After postprocess they must be decoded.
    assert "&amp;" not in text
    assert "&gt;" not in text
    assert "&lt;" not in text


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


def test_convert_one_image_refs_resolve(tmp_path):
    """Regression: image refs in the produced markdown must resolve to real files
    when interpreted relative to the markdown's parent directory.

    Previously, docling's save_as_markdown was given a cwd-relative output path,
    which caused it to both write images to a doubly-nested path AND emit broken
    refs in the .md (refs were resolved against cwd, not the .md's parent dir).
    """
    convert_one(FIXTURE_WITH_IMAGE, tmp_path, with_images=True)
    md_path = tmp_path / "sample_with_image" / "sample_with_image.md"
    assert md_path.is_file()

    text = md_path.read_text()
    refs = re.findall(r"!\[.*?\]\(([^)]+)\)", text)
    assert len(refs) >= 1, f"expected at least one image ref in markdown, got: {text!r}"

    md_dir = md_path.parent
    for ref in refs:
        # Refs must be relative (portable) — not absolute system paths.
        assert not Path(ref).is_absolute(), (
            f"image ref {ref!r} is an absolute path; refs must be relative to "
            f"the markdown's parent directory so the .md is portable"
        )
        resolved = md_dir.joinpath(ref)
        assert resolved.is_file(), (
            f"image ref {ref!r} does not resolve to an existing file "
            f"(resolved to {resolved})"
        )

    # Sanity: there should be NO doubly-nested outputs/<stem>/outputs/... folder
    nested = tmp_path / "sample_with_image" / tmp_path.name
    assert not nested.exists(), (
        f"unexpected nested output dir found at {nested} "
        f"(docling wrote artifacts relative to cwd instead of the .md parent)"
    )


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


def test_convert_batch_isolates_errors(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    shutil.copy(FIXTURE, in_dir / "good.pdf")
    # Write a non-PDF file with .pdf extension to provoke a docling error.
    (in_dir / "broken.pdf").write_text("this is not a real PDF")

    from pdf2md.convert import convert_batch

    summary = convert_batch(in_dir, out_dir)
    assert summary.total == 2
    assert summary.succeeded == 1
    assert summary.failed == 1

    by_name = {r.source.name: r for r in summary.results}
    assert by_name["good.pdf"].status == ConversionStatus.SUCCESS
    assert by_name["broken.pdf"].status == ConversionStatus.FAILED
    assert by_name["broken.pdf"].error is not None
    assert by_name["broken.pdf"].error != ""


def _make_image_files(art_dir: Path, mapping: dict[str, bytes]) -> None:
    art_dir.mkdir(parents=True, exist_ok=True)
    for name, content in mapping.items():
        (art_dir / name).write_bytes(content)


def test_prune_drops_refs_to_recurring_image_content(tmp_path):
    """Images whose bytes recur >= 3 times are page chrome — refs and files go."""
    md = tmp_path / "doc.md"
    art = tmp_path / "doc_artifacts"
    chrome = b"\x89PNG\r\n\x1a\n" + b"chrome-bytes" * 10
    real = b"\x89PNG\r\n\x1a\n" + b"real-content-bytes" * 10
    _make_image_files(
        art,
        {
            "image_001_a.png": chrome,
            "image_002_b.png": chrome,
            "image_003_c.png": chrome,
            "image_004_d.png": real,
        },
    )
    md.write_text(
        "# Title\n\n"
        "Para 1.\n\n"
        "![Image](doc_artifacts/image_001_a.png)\n\n"
        "Para 2.\n\n"
        "![Image](doc_artifacts/image_002_b.png)\n\n"
        "![Image](doc_artifacts/image_004_d.png)\n\n"
        "Para 3.\n\n"
        "![Image](doc_artifacts/image_003_c.png)\n"
    )

    pruned = _prune_repeated_images(md)

    assert pruned == 3
    out = md.read_text()
    assert "image_001_a.png" not in out
    assert "image_002_b.png" not in out
    assert "image_003_c.png" not in out
    assert "image_004_d.png" in out
    assert not (art / "image_001_a.png").exists()
    assert not (art / "image_002_b.png").exists()
    assert not (art / "image_003_c.png").exists()
    assert (art / "image_004_d.png").exists()
    # Body prose untouched.
    assert "Para 1." in out and "Para 2." in out and "Para 3." in out


def test_prune_keeps_images_below_threshold(tmp_path):
    """An image appearing 1 or 2 times stays — only 3+ recurrences are dropped."""
    md = tmp_path / "doc.md"
    art = tmp_path / "doc_artifacts"
    twice = b"twice-content-bytes" * 50
    once = b"once-content-bytes" * 50
    _make_image_files(art, {"image_001_a.png": twice, "image_002_b.png": twice, "image_003_c.png": once})
    md.write_text(
        "![Image](doc_artifacts/image_001_a.png)\n\n"
        "![Image](doc_artifacts/image_002_b.png)\n\n"
        "![Image](doc_artifacts/image_003_c.png)\n"
    )

    pruned = _prune_repeated_images(md)

    assert pruned == 0
    out = md.read_text()
    assert "image_001_a.png" in out
    assert "image_002_b.png" in out
    assert "image_003_c.png" in out


def test_prune_handles_missing_referenced_files(tmp_path):
    """Refs to missing files (e.g. external URLs) are left alone, not crashed on."""
    md = tmp_path / "doc.md"
    md.write_text("![alt](https://example.com/x.png)\n\nbody\n")

    pruned = _prune_repeated_images(md)

    assert pruned == 0
    assert "https://example.com/x.png" in md.read_text()


def test_convert_batch_reuses_single_converter(tmp_path, monkeypatch):
    """Regression: a batch of N PDFs must instantiate the heavy DocumentConverter
    exactly once. Re-creating it per PDF accumulates model state until the OS
    OOM-kills long batches.
    """
    import pdf2md.convert as conv

    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    shutil.copy(FIXTURE, in_dir / "doc-a.pdf")
    shutil.copy(FIXTURE, in_dir / "doc-b.pdf")
    shutil.copy(FIXTURE, in_dir / "doc-c.pdf")

    real_make_converter = conv._make_converter
    calls = {"n": 0}

    def counting_make_converter(*args, **kwargs):
        calls["n"] += 1
        return real_make_converter(*args, **kwargs)

    monkeypatch.setattr(conv, "_make_converter", counting_make_converter)

    summary = conv.convert_batch(in_dir, out_dir)

    assert summary.succeeded == 3
    assert calls["n"] == 1, (
        f"_make_converter was called {calls['n']} times for 3 PDFs; "
        "expected 1 (single shared converter for the whole batch)"
    )


def test_convert_batch_strict_raises(tmp_path):
    import pytest

    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    (in_dir / "broken.pdf").write_text("not a PDF")

    from pdf2md.convert import convert_batch

    with pytest.raises(Exception):
        convert_batch(in_dir, out_dir, strict=True)
