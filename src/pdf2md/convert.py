"""Core conversion logic for pdf2md.

Exposes two pure functions (convert_one, convert_batch) and the result
dataclasses they return. No CLI, logging, or argparse here — this module
is importable as a library.
"""

from __future__ import annotations

import importlib.metadata
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
) -> ConversionResult:
    """Convert a single PDF to markdown.

    Output layout: <output_root>/<stem>/<stem>.md (+ optional <stem>_artifacts/).
    """
    source = Path(source)
    output_root = Path(output_root)
    stem = source.stem
    out_dir = output_root / stem
    out_md = out_dir / f"{stem}.md"

    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    converter = _make_converter(fast_tables=fast_tables, with_images=with_images)
    result = converter.convert(source)
    doc = result.document
    n_pages = len(list(doc.pages))

    image_mode = ImageRefMode.REFERENCED if with_images else ImageRefMode.PLACEHOLDER
    doc.save_as_markdown(out_md, image_mode=image_mode)

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

    elapsed = time.monotonic() - started
    return ConversionResult(
        source=source,
        output_md=out_md,
        status=ConversionStatus.SUCCESS,
        n_pages=n_pages,
        elapsed_s=elapsed,
        error=None,
    )
