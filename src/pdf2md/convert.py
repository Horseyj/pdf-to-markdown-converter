"""Core conversion logic for pdf2md.

Exposes two pure functions (convert_one, convert_batch) and the result
dataclasses they return. No CLI, logging, or argparse here — this module
is importable as a library.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableFormerMode,
    TableStructureOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode


class ConversionStatus(str, Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class ConversionResult:
    source: Path
    output_md: Path
    status: ConversionStatus
    n_pages: int
    elapsed_s: float
    error: str | None


@dataclass(frozen=True)
class BatchSummary:
    succeeded: int
    failed: int
    skipped: int
    elapsed_s: float
    results: list[ConversionResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.succeeded + self.failed + self.skipped


def _make_converter(*, fast_tables: bool = False, with_images: bool = True) -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options = TableStructureOptions(
        do_cell_matching=True,
        mode=TableFormerMode.FAST if fast_tables else TableFormerMode.ACCURATE,
    )
    pipeline_options.generate_picture_images = with_images
    pipeline_options.images_scale = 2.0
    pipeline_options.accelerator_options = AcceleratorOptions(
        num_threads=4,
        device=AcceleratorDevice.AUTO,
    )
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        },
    )


def convert_one(
    source: Path,
    output_root: Path,
    *,
    fast_tables: bool = False,
    with_images: bool = True,
    converter: DocumentConverter | None = None,
) -> ConversionResult:
    """Convert a single PDF to markdown.

    Output layout: <output_root>/<stem>/<stem>.md (+ optional <stem>_artifacts/).

    Pass `converter` to reuse a pre-built `DocumentConverter` across many calls
    (the batch driver does this — it avoids reloading the OCR/layout models per
    PDF, which is both slow and the cause of process-wide memory growth).
    """
    source = Path(source)
    output_root = Path(output_root)
    stem = source.stem
    out_dir = output_root / stem
    out_md = out_dir / f"{stem}.md"

    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    if converter is None:
        converter = _make_converter(fast_tables=fast_tables, with_images=with_images)
    result = converter.convert(source)
    doc = result.document
    n_pages = len(list(doc.pages))

    image_mode = ImageRefMode.REFERENCED if with_images else ImageRefMode.PLACEHOLDER
    # Pass artifacts_dir as a bare relative path (just the basename, no parent).
    # docling's _get_output_paths then sets reference_path = out_md.parent and
    # places artifacts at out_md.parent / artifacts_dir, which (a) avoids the
    # doubly-nested path that occurs when out_md is cwd-relative and (b) makes
    # image refs in the produced markdown relative to the .md's parent dir,
    # so the .md remains portable.
    doc.save_as_markdown(
        out_md,
        artifacts_dir=Path(f"{stem}_artifacts"),
        image_mode=image_mode,
    )

    # Prepend provenance header. Order: source, pages, extractor.
    docling_version = importlib.metadata.version("docling")
    header = (
        f"<!-- source: {source.name} -->\n"
        f"<!-- pages: {n_pages} -->\n"
        f"<!-- extractor: docling {docling_version} -->\n"
        f"\n"
    )
    body = out_md.read_text()
    out_md.write_text(header + body)

    if with_images:
        _prune_repeated_images(out_md)

    elapsed = time.monotonic() - started
    return ConversionResult(
        source=source,
        output_md=out_md,
        status=ConversionStatus.SUCCESS,
        n_pages=n_pages,
        elapsed_s=elapsed,
        error=None,
    )


_IMAGE_REF_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def _prune_repeated_images(md_path: Path, *, min_repetitions: int = 3) -> int:
    """Drop image references whose underlying file content recurs `min_repetitions`
    or more times — these are page chrome (footers, dividers, decorative icons)
    that add visual noise without information.

    Identity is content hash, not filename, because docling assigns each extracted
    image a unique numbered filename even when the bytes are identical. Refs that
    point outside the markdown's directory or to missing files are left untouched.

    Returns the number of ref lines removed.
    """
    text = md_path.read_text()
    md_dir = md_path.parent

    hash_by_relpath: dict[str, str] = {}
    refs_per_hash: dict[str, int] = {}
    for match in _IMAGE_REF_RE.finditer(text):
        relpath = match.group(1)
        if relpath in hash_by_relpath:
            refs_per_hash[hash_by_relpath[relpath]] += 1
            continue
        target = md_dir / relpath
        if not target.is_file():
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        hash_by_relpath[relpath] = digest
        refs_per_hash[digest] = refs_per_hash.get(digest, 0) + 1

    decorative_hashes = {h for h, n in refs_per_hash.items() if n >= min_repetitions}
    if not decorative_hashes:
        return 0

    decorative_relpaths = {
        rp for rp, h in hash_by_relpath.items() if h in decorative_hashes
    }

    def _is_decorative_line(line: str) -> bool:
        stripped = line.strip()
        m = _IMAGE_REF_RE.fullmatch(stripped)
        return m is not None and m.group(1) in decorative_relpaths

    kept_lines = [ln for ln in text.splitlines(keepends=True) if not _is_decorative_line(ln)]
    pruned = len(text.splitlines(keepends=True)) - len(kept_lines)
    md_path.write_text("".join(kept_lines))

    for rp in decorative_relpaths:
        target = md_dir / rp
        try:
            target.unlink()
        except FileNotFoundError:
            pass

    return pruned


def _discover_pdfs(in_dir: Path) -> list[Path]:
    """Non-recursive, case-insensitive *.pdf discovery, sorted by name."""
    return sorted(p for p in in_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


def convert_batch(
    in_dir: Path,
    out_dir: Path,
    *,
    force: bool = False,
    strict: bool = False,
    fast_tables: bool = False,
    with_images: bool = True,
    on_progress: "callable | None" = None,
) -> BatchSummary:
    """Convert every PDF in `in_dir` (non-recursive) into `out_dir/<stem>/<stem>.md`.

    `on_progress(index, total, result)` is called after each PDF (success, skip,
    or fail) for progress display. The CLI passes a logging callback; tests pass
    None.
    """
    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = _discover_pdfs(in_dir)
    results: list[ConversionResult] = []
    started = time.monotonic()

    # Build the converter once and reuse it for the whole batch. Re-creating it
    # per PDF accumulates ~hundreds of MB of model state across iterations
    # because Python/PyTorch don't release the previous instance promptly,
    # which has OOM-killed long batches on machines with 16GB RAM. Reuse also
    # eliminates the multi-second model-load phase from every iteration.
    converter: DocumentConverter | None = None

    for i, pdf in enumerate(pdfs, start=1):
        out_md = out_dir / pdf.stem / f"{pdf.stem}.md"
        if out_md.exists() and not force:
            result = ConversionResult(
                source=pdf,
                output_md=out_md,
                status=ConversionStatus.SKIPPED,
                n_pages=0,
                elapsed_s=0.0,
                error=None,
            )
        else:
            if converter is None:
                converter = _make_converter(fast_tables=fast_tables, with_images=with_images)
            try:
                result = convert_one(
                    pdf,
                    out_dir,
                    fast_tables=fast_tables,
                    with_images=with_images,
                    converter=converter,
                )
            except Exception as exc:
                if strict:
                    raise
                result = ConversionResult(
                    source=pdf,
                    output_md=out_dir / pdf.stem / f"{pdf.stem}.md",
                    status=ConversionStatus.FAILED,
                    n_pages=0,
                    elapsed_s=0.0,
                    error=f"{type(exc).__name__}: {exc}",
                )
        results.append(result)
        if on_progress is not None:
            on_progress(i, len(pdfs), result)

    elapsed = time.monotonic() - started
    succeeded = sum(1 for r in results if r.status == ConversionStatus.SUCCESS)
    failed = sum(1 for r in results if r.status == ConversionStatus.FAILED)
    skipped = sum(1 for r in results if r.status == ConversionStatus.SKIPPED)
    return BatchSummary(
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        elapsed_s=elapsed,
        results=results,
    )
