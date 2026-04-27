# pdf2md Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lean, production-grade Python utility (`pdf2md`) that converts PDFs (clean digital, scanned, hairy real-world educational/guide content) to clean markdown for human and LLM consumption.

**Architecture:** Single Python package with one CLI entry point and two run modes (single-PDF and batch). Wraps the [docling](https://github.com/docling-project/docling) library (IBM Research) configured for CPU mode with OCR enabled and TableFormer in ACCURATE mode. Per-PDF self-contained output folder containing a markdown file plus a sidecar artifacts folder for extracted images. Discovery is non-recursive; per-PDF errors do not abort the batch.

**Tech Stack:**
- Python 3.11+
- [docling](https://pypi.org/project/docling/) — PDF → markdown conversion engine
- argparse (stdlib) — CLI
- pytest — testing
- reportlab — generating the test fixture PDF (one-time, not a runtime or test dep)
- GitHub Actions — CI

---

## Working Directory

All paths in this plan are relative to: `/home/jhorsey/repos/automations/pdf-to-md-converter/`

The repo has been initialized with one commit (the design spec). Run all commands from this directory unless otherwise noted.

---

## File Structure (locked before tasks begin)

```
pdf-to-md-converter/
├── README.md                        # Task 16
├── LICENSE                          # Task 1 (MIT)
├── pyproject.toml                   # Task 1
├── Makefile                         # Task 1
├── .gitignore                       # Task 1
├── pdfs/.gitkeep                    # Task 1 (default input drop, contents gitignored)
├── outputs/.gitkeep                 # Task 1 (default output land, contents gitignored)
├── src/pdf2md/
│   ├── __init__.py                  # Task 1 (version export only)
│   ├── __main__.py                  # Task 1 (calls cli.main)
│   ├── cli.py                       # Tasks 12–15 (argparse + entry point)
│   └── convert.py                   # Tasks 4–11 (convert_one + convert_batch)
├── tests/
│   ├── fixtures/sample.pdf          # Task 2 (generated, committed binary)
│   └── test_convert.py              # Tasks 4, 5, 6, 8, 9, 10, 12, 13
├── docs/superpowers/
│   ├── specs/2026-04-27-pdf2md-design.md   # already exists (root commit)
│   └── plans/2026-04-27-pdf2md-implementation.md  # this file
└── .github/workflows/test.yml       # Task 17
```

**File responsibilities:**

- `src/pdf2md/__init__.py` — exports `__version__` only. No logic.
- `src/pdf2md/__main__.py` — single line: `from pdf2md.cli import main; main()`. Enables `python -m pdf2md`.
- `src/pdf2md/cli.py` — argparse, argument resolution (single vs batch), delegates to `convert.py`. Owns the `pdf2md` console-script entry point.
- `src/pdf2md/convert.py` — pure conversion logic. Two public functions (`convert_one`, `convert_batch`) and two dataclasses (`ConversionResult`, `BatchSummary`). No CLI, logging, or argparse. Importable as a library.

If `cli.py` or `convert.py` exceeds ~250 lines during implementation, split it. The split point will be obvious by then.

---

## Task 1: Project scaffolding + dependency install verification

**Files:**
- Create: `LICENSE`
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `.gitignore`
- Create: `pdfs/.gitkeep`
- Create: `outputs/.gitkeep`
- Create: `src/pdf2md/__init__.py`
- Create: `src/pdf2md/__main__.py`
- Create: `tests/__init__.py` (empty, marks tests as a package)

- [ ] **Step 1: Create `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 James H

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "pdf2md"
version = "0.1.0"
description = "Convert PDFs to clean markdown using docling. Single command, batch and single-PDF modes, self-contained per-PDF output."
readme = "README.md"
requires-python = ">=3.11"
license = { file = "LICENSE" }
authors = [{ name = "James H" }]
keywords = ["pdf", "markdown", "docling", "ocr", "document-conversion"]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Topic :: Text Processing :: Markup :: Markdown",
]
dependencies = [
    "docling>=2,<3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
]

[project.scripts]
pdf2md = "pdf2md.cli:main"

[project.urls]
Homepage = "https://github.com/Horseyj/pdf-to-md-converter"
Repository = "https://github.com/Horseyj/pdf-to-md-converter"
Issues = "https://github.com/Horseyj/pdf-to-md-converter/issues"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

- [ ] **Step 3: Create `Makefile`**

```makefile
.PHONY: install install-cpu test convert clean

# Default: GPU PyTorch wheels (~2GB). Works on any system.
install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"

# CPU-only PyTorch wheels (~200MB). Linux only. Use on machines without an NVIDIA GPU.
install-cpu:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]" --extra-index-url https://download.pytorch.org/whl/cpu

test:
	.venv/bin/pytest -v

convert:
	.venv/bin/pdf2md

clean:
	rm -rf .venv build dist *.egg-info src/*.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
```

- [ ] **Step 4: Create `.gitignore`**

```
# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
build/
dist/
.venv/
venv/
.env

# OS
.DS_Store
Thumbs.db

# Tooling
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Workspace data — never commit user PDFs or outputs
pdfs/*
!pdfs/.gitkeep
outputs/*
!outputs/.gitkeep
```

- [ ] **Step 5: Create `pdfs/.gitkeep` and `outputs/.gitkeep`**

Both files are empty (zero bytes). Create with:

```bash
mkdir -p pdfs outputs
touch pdfs/.gitkeep outputs/.gitkeep
```

- [ ] **Step 6: Create `src/pdf2md/__init__.py`**

```python
"""pdf2md — convert PDFs to clean markdown using docling."""

__version__ = "0.1.0"
```

- [ ] **Step 7: Create `src/pdf2md/__main__.py`**

```python
"""Enable `python -m pdf2md`."""

from pdf2md.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Create `tests/__init__.py`**

Empty file. Just makes `tests/` a package.

```bash
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 9: Install in CPU mode and verify**

```bash
make install-cpu
```

Expected: venv created at `.venv/`, deps install without error, finishes with `Successfully installed ... docling-X.Y.Z ...`.

- [ ] **Step 10: Verify the package imports**

```bash
.venv/bin/python -c "import pdf2md; print(pdf2md.__version__)"
```

Expected output: `0.1.0`

- [ ] **Step 11: Verify the CLI entry point exists (will fail with ImportError on cli.main since cli.py doesn't exist yet — this is the intended state at this point)**

```bash
.venv/bin/pdf2md --help 2>&1 | head -5
```

Expected: ImportError or ModuleNotFoundError mentioning `pdf2md.cli`. This confirms the entry point is registered; the missing module is filled in by Task 12.

- [ ] **Step 12: Commit**

```bash
git add LICENSE pyproject.toml Makefile .gitignore pdfs/.gitkeep outputs/.gitkeep src/pdf2md/__init__.py src/pdf2md/__main__.py tests/__init__.py
git commit -m "$(cat <<'EOF'
Bootstrap pdf2md package scaffolding

LICENSE (MIT), pyproject.toml with docling dep and pdf2md entry point,
Makefile with install/install-cpu/test/convert targets, .gitignore that
keeps user PDFs and outputs out of git, empty src/pdf2md package skeleton.
Verified docling installs cleanly via make install-cpu.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Sample test PDF fixture

**Files:**
- Create: `tests/fixtures/sample.pdf` (binary, ~5–20KB, generated once)
- Create: `tests/fixtures/.gitkeep` (only if `sample.pdf` is excluded for some reason; otherwise unnecessary)

**Why this approach:** The fixture is a tiny, deterministic, public-domain (we authored it) 2-page PDF generated once via reportlab and committed as a binary. Reportlab is *not* a project dependency or dev dependency — it is used only at fixture-creation time. If we ever need to regenerate, the script in step 1 documents how.

- [ ] **Step 1: Install reportlab into the venv (temporary, not pinned)**

```bash
.venv/bin/pip install reportlab
```

Expected: install succeeds.

- [ ] **Step 2: Generate the fixture PDF**

```bash
mkdir -p tests/fixtures
.venv/bin/python - <<'PY'
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

path = "tests/fixtures/sample.pdf"
c = canvas.Canvas(path, pagesize=letter)

# Page 1 — heading + body paragraph
c.setFont("Helvetica-Bold", 18)
c.drawString(72, 720, "Sample Document for pdf2md Tests")
c.setFont("Helvetica", 12)
c.drawString(72, 690, "This is page one. It contains a heading and a short body paragraph.")
c.drawString(72, 670, "The text is deterministic so test assertions can match it exactly.")
c.showPage()

# Page 2 — second heading + body
c.setFont("Helvetica-Bold", 14)
c.drawString(72, 720, "Section Two")
c.setFont("Helvetica", 12)
c.drawString(72, 690, "This is page two. It exists so the page count assertion is meaningful.")
c.save()
print(f"wrote {path}")
PY
```

Expected: prints `wrote tests/fixtures/sample.pdf`.

- [ ] **Step 3: Verify the fixture has 2 pages**

```bash
.venv/bin/python -c "
import docling.datamodel.base_models as b
from docling.document_converter import DocumentConverter
r = DocumentConverter().convert('tests/fixtures/sample.pdf')
print('pages:', len(list(r.document.pages)))
print('status:', r.status)
"
```

Expected: `pages: 2` and `status: ConversionStatus.SUCCESS` (the first run downloads docling models — may take 1–3 minutes; subsequent runs are fast).

- [ ] **Step 4: Uninstall reportlab to keep the venv lean**

```bash
.venv/bin/pip uninstall -y reportlab
```

Expected: reportlab removed.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/sample.pdf
git commit -m "$(cat <<'EOF'
Add deterministic 2-page test fixture PDF

Generated once via reportlab. Reportlab is not a project dep — only the
output binary is committed. Page 1 has a heading + body paragraph,
page 2 has a second heading + body. Used by all convert tests.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: ConversionResult and BatchSummary dataclasses

**Files:**
- Create: `src/pdf2md/convert.py`
- Modify: `tests/test_convert.py` (create if missing)

These types are used by `convert_one` (Task 4) and `convert_batch` (Task 7). Defining them first keeps later tasks readable.

- [ ] **Step 1: Write the failing test**

Create `tests/test_convert.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/test_convert.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pdf2md.convert'`.

- [ ] **Step 3: Create `src/pdf2md/convert.py` with the dataclasses**

```python
"""Core conversion logic for pdf2md.

Exposes two pure functions (convert_one, convert_batch) and the result
dataclasses they return. No CLI, logging, or argparse here — this module
is importable as a library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


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
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
.venv/bin/pytest tests/test_convert.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/pdf2md/convert.py tests/test_convert.py
git commit -m "$(cat <<'EOF'
Add ConversionResult and BatchSummary dataclasses

Frozen dataclasses with explicit ConversionStatus enum (SUCCESS, SKIPPED,
FAILED). BatchSummary exposes total via property to avoid drift.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: convert_one() — happy path

**Files:**
- Modify: `src/pdf2md/convert.py`
- Modify: `tests/test_convert.py`

Implements the core single-PDF conversion: takes a PDF path and an output root, returns a `ConversionResult`, writes the markdown file. No header comments yet (Task 5), no images yet (Task 6).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_convert.py`:

```python
import time

from pdf2md.convert import convert_one

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/test_convert.py::test_convert_one_writes_markdown -v
```

Expected: FAIL with `ImportError: cannot import name 'convert_one'`.

- [ ] **Step 3: Implement `convert_one` in `src/pdf2md/convert.py`**

Append to `src/pdf2md/convert.py`:

```python
import time

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableFormerMode,
    TableStructureOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode


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

    elapsed = time.monotonic() - started
    return ConversionResult(
        source=source,
        output_md=out_md,
        status=ConversionStatus.SUCCESS,
        n_pages=n_pages,
        elapsed_s=elapsed,
        error=None,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/pytest tests/test_convert.py -v
```

Expected: 4 tests pass. The convert tests may take 30–90 seconds each (docling does real work).

- [ ] **Step 5: Commit**

```bash
git add src/pdf2md/convert.py tests/test_convert.py
git commit -m "$(cat <<'EOF'
Implement convert_one happy path

Wraps docling's DocumentConverter with our chosen defaults (OCR on,
TableFormer ACCURATE, image generation on). Writes output to
<root>/<stem>/<stem>.md using ImageRefMode.REFERENCED so images land
in a sidecar folder with relative refs in the markdown.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: convert_one() — provenance header comments

**Files:**
- Modify: `src/pdf2md/convert.py`
- Modify: `tests/test_convert.py`

Each output `.md` must begin with three HTML comments: source filename, page count, extractor + version. No timestamp (must be deterministic across re-runs).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_convert.py`:

```python
import importlib.metadata


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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/test_convert.py::test_convert_one_writes_provenance_header -v
```

Expected: FAIL — assertion error because the file does not yet start with the provenance header.

- [ ] **Step 3: Modify `convert_one` in `src/pdf2md/convert.py` to prepend the header**

Add this import at the top of the file (alongside the other imports):

```python
import importlib.metadata
```

Replace the `doc.save_as_markdown(...)` block in `convert_one` with:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/pytest tests/test_convert.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/pdf2md/convert.py tests/test_convert.py
git commit -m "$(cat <<'EOF'
Prepend provenance header to converted markdown

Three HTML comments at the top of every .md: source filename, page count,
docling version. No timestamp — outputs are byte-identical across re-runs
of the same input, which keeps them diffable in git.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: convert_one() — image sidecar verification

**Files:**
- Modify: `tests/test_convert.py`

`convert_one` already writes images via `ImageRefMode.REFERENCED` (Task 4). This task adds a test that confirms the sidecar folder is created when images are present, and that `--no-images` (i.e. `with_images=False`) suppresses it. The fixture has no embedded images, so we test the suppression branch directly and the presence branch by inspecting docling's output structure on the fixture (which still creates an empty sidecar dir or no dir depending on docling's behavior; the test is tolerant).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_convert.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify both pass**

```bash
.venv/bin/pytest tests/test_convert.py -v
```

Expected: 8 tests pass. (No code change needed — `with_images` is already a parameter from Task 4.)

If the assertion in `test_convert_one_no_images_suppresses_sidecar` fails because docling created an empty folder, that's still acceptable — the test allows it. If it fails because docling created images even with `generate_picture_images=False`, that's a real bug; investigate the docling version's actual behavior for `ImageRefMode.PLACEHOLDER` and adjust.

- [ ] **Step 3: Commit (no code change, just a behavior-locking test)**

```bash
git add tests/test_convert.py
git commit -m "$(cat <<'EOF'
Lock convert_one image-sidecar behavior with tests

Confirms with_images=True doesn't error on the fixture (which has no
embedded images), and that with_images=False suppresses the sidecar
artifacts folder (or leaves it empty).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: convert_batch() — happy path

**Files:**
- Modify: `src/pdf2md/convert.py`
- Modify: `tests/test_convert.py`

Walks an input directory non-recursively for `*.pdf`, calls `convert_one` on each, returns a `BatchSummary`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_convert.py`:

```python
import shutil


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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/pytest tests/test_convert.py::test_convert_batch_happy_path -v
```

Expected: FAIL with `ImportError: cannot import name 'convert_batch'`.

- [ ] **Step 3: Implement `convert_batch` in `src/pdf2md/convert.py`**

Append to `src/pdf2md/convert.py`:

```python
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

    for i, pdf in enumerate(pdfs, start=1):
        result = convert_one(
            pdf, out_dir, fast_tables=fast_tables, with_images=with_images
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
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/pytest tests/test_convert.py -v
```

Expected: 10 tests pass. Batch tests will take ~1–3 minutes each because they convert two PDFs.

- [ ] **Step 5: Commit**

```bash
git add src/pdf2md/convert.py tests/test_convert.py
git commit -m "$(cat <<'EOF'
Implement convert_batch happy path

Non-recursive *.pdf discovery (case-insensitive, sorted), iterates
convert_one over each, returns a BatchSummary with per-PDF results.
Optional on_progress callback for CLI logging.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: convert_batch() — skip-existing + force flag

**Files:**
- Modify: `src/pdf2md/convert.py`
- Modify: `tests/test_convert.py`

If the output `.md` already exists, skip the conversion (return `ConversionStatus.SKIPPED`). `force=True` overrides the skip and re-converts.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_convert.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/pytest tests/test_convert.py::test_convert_batch_skips_existing -v
```

Expected: FAIL — `second.skipped == 0` (currently re-converts unconditionally).

- [ ] **Step 3: Modify `convert_batch` to skip when output exists (unless force)**

Replace the loop body inside `convert_batch` with:

```python
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
            result = convert_one(
                pdf, out_dir, fast_tables=fast_tables, with_images=with_images
            )
        results.append(result)
        if on_progress is not None:
            on_progress(i, len(pdfs), result)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/pytest tests/test_convert.py -v
```

Expected: 12 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/pdf2md/convert.py tests/test_convert.py
git commit -m "$(cat <<'EOF'
Skip already-converted PDFs in batch mode (force overrides)

If <out>/<stem>/<stem>.md already exists, skip conversion and emit a
SKIPPED ConversionResult. `force=True` re-converts unconditionally.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: convert_batch() — per-PDF error isolation + strict mode

**Files:**
- Modify: `src/pdf2md/convert.py`
- Modify: `tests/test_convert.py`

A failure on one PDF must not abort the rest of the batch (default behavior). `strict=True` re-raises on first failure (for CI).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_convert.py`:

```python
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


def test_convert_batch_strict_raises(tmp_path):
    import pytest

    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    (in_dir / "broken.pdf").write_text("not a PDF")

    from pdf2md.convert import convert_batch

    with pytest.raises(Exception):
        convert_batch(in_dir, out_dir, strict=True)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/pytest tests/test_convert.py::test_convert_batch_isolates_errors -v
```

Expected: FAIL — currently the broken PDF raises an exception that aborts the batch.

- [ ] **Step 3: Wrap the per-PDF call in try/except inside `convert_batch`**

Replace the `else:` branch from Task 8 with:

```python
        else:
            try:
                result = convert_one(
                    pdf, out_dir, fast_tables=fast_tables, with_images=with_images
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
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/pytest tests/test_convert.py -v
```

Expected: 14 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/pdf2md/convert.py tests/test_convert.py
git commit -m "$(cat <<'EOF'
Isolate per-PDF errors in batch (strict mode opts back into fail-fast)

Default: a failure on one PDF logs as FAILED in the result and the
batch continues. strict=True re-raises immediately, useful in CI.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: CLI argparse skeleton + version flag

**Files:**
- Create: `src/pdf2md/cli.py`
- Modify: `tests/test_convert.py` (rename to `tests/test_cli.py` for the new tests, OR add CLI tests inline — for simplicity, add to a new file)
- Create: `tests/test_cli.py`

Stand up the CLI with no real wiring to convert.py yet. `pdf2md --help` and `pdf2md --version` work; everything else exits with a helpful error.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli.py`:

```python
"""Tests for pdf2md.cli."""

import subprocess
import sys


def run_cli(*args, cwd=None):
    """Invoke the CLI as a subprocess so we exercise the real entry point."""
    return subprocess.run(
        [sys.executable, "-m", "pdf2md", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_cli_version():
    r = run_cli("--version")
    assert r.returncode == 0
    assert "pdf2md" in r.stdout
    assert "0.1.0" in r.stdout


def test_cli_help():
    r = run_cli("--help")
    assert r.returncode == 0
    assert "pdf2md" in r.stdout
    assert "--in" in r.stdout
    assert "--out" in r.stdout
    assert "--force" in r.stdout
    assert "--strict" in r.stdout
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/pytest tests/test_cli.py -v
```

Expected: FAIL — `python -m pdf2md` raises ImportError because `cli.py` doesn't exist.

- [ ] **Step 3: Create `src/pdf2md/cli.py`**

```python
"""Command-line interface for pdf2md."""

from __future__ import annotations

import argparse
import sys

from pdf2md import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf2md",
        description=(
            "Convert PDFs to clean markdown using docling. "
            "Run with no arguments for batch mode (./pdfs -> ./outputs), "
            "or pass a single PDF path."
        ),
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help=(
            "Path to a single PDF (single-PDF mode) or a directory "
            "(batch mode, equivalent to --in DIR). "
            "Omit for batch mode using --in (default ./pdfs)."
        ),
    )
    parser.add_argument("--in", dest="in_dir", default="pdfs", help="Batch input directory (default: ./pdfs)")
    parser.add_argument("--out", dest="out_dir", default="outputs", help="Output directory (default: ./outputs)")
    parser.add_argument("--force", action="store_true", help="Re-convert even if output already exists")
    parser.add_argument("--fast", action="store_true", help="Use FAST table mode instead of ACCURATE")
    parser.add_argument("--no-images", dest="with_images", action="store_false", help="Skip image extraction")
    parser.add_argument("--strict", action="store_true", help="Fail-fast on first error (for CI)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--version", action="version", version=f"pdf2md {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Wiring to convert.py happens in Task 11.
    print("pdf2md: CLI not yet wired (Task 11). Args parsed:", vars(args), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/pytest tests/test_cli.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/pdf2md/cli.py tests/test_cli.py
git commit -m "$(cat <<'EOF'
Stand up CLI skeleton with --help and --version

argparse with all flags wired (in/out/force/fast/no-images/strict/verbose),
no real conversion logic yet — that lands in the next task. --version
and --help work; any other invocation exits 2 with a placeholder message.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: CLI — wire single-PDF and batch modes + progress + exit codes

**Files:**
- Modify: `src/pdf2md/cli.py`
- Modify: `tests/test_cli.py`

Resolves the positional `input` argument (file vs directory vs absent), calls `convert_one` or `convert_batch`, prints per-PDF progress lines, prints final summary, returns the right exit code.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
import shutil
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_cli_single_pdf_mode(tmp_path):
    out_dir = tmp_path / "out"
    r = run_cli(str(FIXTURE), "--out", str(out_dir))
    assert r.returncode == 0, r.stderr
    assert (out_dir / "sample" / "sample.md").is_file()


def test_cli_batch_mode(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    shutil.copy(FIXTURE, in_dir / "doc-a.pdf")
    shutil.copy(FIXTURE, in_dir / "doc-b.pdf")

    r = run_cli("--in", str(in_dir), "--out", str(out_dir))
    assert r.returncode == 0, r.stderr
    assert (out_dir / "doc-a" / "doc-a.md").is_file()
    assert (out_dir / "doc-b" / "doc-b.md").is_file()


def test_cli_directory_as_positional_is_batch(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    shutil.copy(FIXTURE, in_dir / "x.pdf")

    r = run_cli(str(in_dir), "--out", str(out_dir))
    assert r.returncode == 0, r.stderr
    assert (out_dir / "x" / "x.md").is_file()


def test_cli_exit_code_on_failure(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    (in_dir / "broken.pdf").write_text("not a PDF")

    r = run_cli("--in", str(in_dir), "--out", str(out_dir))
    assert r.returncode == 1, f"expected 1, got {r.returncode}; stderr={r.stderr}"


def test_cli_exit_code_on_invocation_error(tmp_path):
    r = run_cli("--in", str(tmp_path / "does-not-exist"), "--out", str(tmp_path / "out"))
    assert r.returncode == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/pytest tests/test_cli.py -v
```

Expected: FAIL — the placeholder `main` returns 2 for everything.

- [ ] **Step 3: Replace `main` in `src/pdf2md/cli.py`**

Replace the `main` function with this (keep `build_parser` as-is):

```python
from pathlib import Path

from pdf2md.convert import (
    BatchSummary,
    ConversionResult,
    ConversionStatus,
    convert_batch,
    convert_one,
)


def _format_progress(i: int, total: int, result: ConversionResult) -> str:
    if result.status == ConversionStatus.SUCCESS:
        return f"[{i}/{total}] {result.source.name} -> {result.output_md.parent}/ ({result.elapsed_s:.1f}s, {result.n_pages} pages)"
    if result.status == ConversionStatus.SKIPPED:
        return f"[{i}/{total}] SKIP {result.source.name} (output exists, use --force to overwrite)"
    return f"[{i}/{total}] FAILED {result.source.name}: {result.error}"


def _print_progress(i: int, total: int, result: ConversionResult) -> None:
    line = _format_progress(i, total, result)
    stream = sys.stderr if result.status == ConversionStatus.FAILED else sys.stdout
    print(line, file=stream)


def _print_summary(summary: BatchSummary, out_dir: Path) -> None:
    print(
        f"\n{summary.succeeded} succeeded, {summary.failed} failed, {summary.skipped} skipped"
    )
    mins, secs = divmod(int(summary.elapsed_s), 60)
    print(f"Total time: {mins}m {secs}s")
    print(f"Output: {out_dir}/")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)

    # Resolve mode: positional input takes precedence over --in.
    positional = Path(args.input) if args.input else None

    if positional is not None and positional.is_file():
        # Single-PDF mode.
        try:
            result = convert_one(
                positional,
                out_dir,
                fast_tables=args.fast,
                with_images=args.with_images,
            )
        except Exception as exc:
            print(f"FAILED {positional.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(_format_progress(1, 1, result))
        return 0 if result.status == ConversionStatus.SUCCESS else 1

    # Batch mode. Source dir = positional (if directory) else --in.
    if positional is not None and positional.is_dir():
        in_dir = positional
    elif positional is not None:
        print(f"pdf2md: input not found: {positional}", file=sys.stderr)
        return 2
    else:
        in_dir = Path(args.in_dir)

    if not in_dir.is_dir():
        print(f"pdf2md: input directory not found: {in_dir}", file=sys.stderr)
        return 2

    try:
        summary = convert_batch(
            in_dir,
            out_dir,
            force=args.force,
            strict=args.strict,
            fast_tables=args.fast,
            with_images=args.with_images,
            on_progress=_print_progress,
        )
    except Exception as exc:
        print(f"pdf2md: batch aborted: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    _print_summary(summary, out_dir)
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/pytest tests/test_cli.py -v
```

Expected: 7 CLI tests pass.

- [ ] **Step 5: Run the full test suite**

```bash
.venv/bin/pytest -v
```

Expected: 14 convert tests + 7 CLI tests = 21 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/pdf2md/cli.py tests/test_cli.py
git commit -m "$(cat <<'EOF'
Wire CLI to convert_one / convert_batch with progress + exit codes

Resolves positional input as file (single-PDF) or directory (batch),
falls back to --in default ./pdfs. Per-PDF progress lines on stdout
(stderr for failures), final summary always printed. Exit codes:
0 = all good, 1 = any failure, 2 = invocation error (bad args).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: README

**Files:**
- Create: `README.md`

Single-page README. No marketing fluff, no emojis. Covers: what it is, install, usage, supported PDF types, limitations, engine credit, license.

- [ ] **Step 1: Create `README.md`**

```markdown
# pdf2md

Convert PDFs to clean markdown using [docling](https://github.com/docling-project/docling). Single command, batch and single-PDF modes, self-contained per-PDF output. Handles digital PDFs, scanned PDFs (OCR), and complex layouts (tables, images).

## Install

Requires Python 3.11 or newer.

```bash
git clone https://github.com/Horseyj/pdf-to-md-converter.git
cd pdf-to-md-converter
make install-cpu     # for laptops without an NVIDIA GPU (~200MB)
# or:
make install         # default; pulls GPU PyTorch wheels (~2GB)
```

This creates a `.venv/` and installs `pdf2md` as a console script. After install, activate the venv (`source .venv/bin/activate`) so the `pdf2md` command is on your PATH, or run it directly as `.venv/bin/pdf2md`.

## Usage

### Batch mode (default)

Drop PDFs into `./pdfs/`, run:

```bash
pdf2md
```

Outputs land in `./outputs/<pdf-stem>/<pdf-stem>.md` plus a sidecar `<pdf-stem>_artifacts/` folder for any extracted images.

### Single PDF

```bash
pdf2md path/to/document.pdf
```

### Custom paths

```bash
pdf2md --in ~/Documents/MyPDFs --out ~/Desktop/Converted
```

### Re-convert (overwrite existing output)

```bash
pdf2md --force
```

## CLI reference

```
pdf2md [INPUT] [options]

Positional:
  INPUT           Path to a single PDF, or a directory (batch mode).
                  Omit for batch mode using --in (default ./pdfs).

Options:
  --in DIR        Batch input directory (default: ./pdfs)
  --out DIR       Output directory (default: ./outputs)
  --force         Re-convert even if output already exists
  --fast          Use FAST table mode instead of ACCURATE (faster, less precise)
  --no-images     Skip image extraction
  --strict        Fail-fast on first error (for CI)
  -v, --verbose   Verbose logging
  --version       Print version and exit
  -h, --help      Show help
```

## Output structure

For each `foo.pdf`:

```
outputs/foo/
├── foo.md
└── foo_artifacts/        # only if the PDF contains extractable images
    ├── image_000000_<hash>.png
    └── ...
```

Each `.md` begins with three HTML comments recording the source filename, page count, and docling version used. Outputs are deterministic — re-running `pdf2md` on the same input produces a byte-identical `.md` (no timestamps).

## Supported PDF types

- Born-digital PDFs (text-extractable)
- Scanned PDFs (OCR runs by default; quality depends on scan resolution)
- PDFs with tables (extracted via docling's TableFormer)
- PDFs with images (saved to the sidecar artifacts folder by default)

## Known limitations

- Math/equation extraction quality varies; complex math may need manual review.
- Very large PDFs (500+ pages) take a long time on CPU. Use a machine with a GPU and `make install` (default install) for substantially faster conversions.
- Non-Latin scripts work via OCR but accuracy depends on the OCR engine docling uses.
- Forms and structured documents are not specifically optimized for.
- Page anchors (`<!-- page N -->` comments) are not emitted in v1; deferred to a later release.

## License

MIT. See `LICENSE`.

## Credits

Built on [docling](https://github.com/docling-project/docling) (IBM Research).
```

- [ ] **Step 2: Verify it renders correctly (optional, manual)**

Open `README.md` in any markdown viewer or push to a fork to inspect on GitHub. No CI assertion.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
Add README

Single-page docs: install (CPU and default), usage (batch, single, custom
paths, force), CLI reference, output structure, supported PDF types,
known limitations, license, engine credit.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: GitHub Actions CI

**Files:**
- Create: `.github/workflows/test.yml`

Run pytest on every push, on Python 3.11 and 3.12. Use the CPU-wheels install path (CI machines have no GPU).

- [ ] **Step 1: Create the workflow file**

```yaml
name: tests

on:
  push:
    branches: ["**"]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install dependencies (CPU PyTorch wheels)
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]" --extra-index-url https://download.pytorch.org/whl/cpu

      - name: Run tests
        run: pytest -v
```

- [ ] **Step 2: Commit**

```bash
mkdir -p .github/workflows
git add .github/workflows/test.yml
git commit -m "$(cat <<'EOF'
Add GitHub Actions CI workflow

Runs pytest on push and PR, Python 3.11 and 3.12, Ubuntu latest.
Installs with CPU PyTorch wheels because CI runners have no GPU.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

(Note: CI will only actually run after the repo is pushed to GitHub. That happens in Task 14.)

---

## Task 14: End-to-end smoke test on a real PDF + push to GitHub

**Files:** none modified

This task is half manual: run pdf2md on a real PDF the user has on hand, eyeball the output, then push to GitHub.

- [ ] **Step 1: Create an empty private/public repo on GitHub**

User action (does not require code changes). Suggested name: `pdf-to-md-converter`. Either privacy setting is fine; can be flipped to public later.

- [ ] **Step 2: Add the GitHub remote and push**

```bash
git remote add origin git@github.com:Horseyj/pdf-to-md-converter.git
git push -u origin main
```

Expected: push succeeds. CI workflow starts on push.

- [ ] **Step 3: Drop one of the user's actual 15 PDFs into `./pdfs/`**

User action. Pick the smallest one for the smoke test. (`./pdfs/` is gitignored — the file will not be committed.)

- [ ] **Step 4: Run the converter**

```bash
make convert
```

Expected: progress line, then summary. Output appears in `./outputs/<stem>/<stem>.md`.

- [ ] **Step 5: Open the output markdown and eyeball it**

Open `./outputs/<stem>/<stem>.md` in any markdown viewer. Check:
- Headings preserved
- Paragraphs in the right order
- Tables (if any) rendered as markdown tables
- Images (if any) referenced correctly from `<stem>_artifacts/` and visible

If output looks broken: file an issue, do NOT proceed to Task 15. The implementation has a real defect.

If output looks clean: proceed.

- [ ] **Step 6: Verify CI passed on GitHub**

Open `https://github.com/Horseyj/pdf-to-md-converter/actions` and confirm the most recent workflow run is green.

If CI failed: investigate the failure, fix, push, re-check.

- [ ] **Step 7: Tag v0.1.0 and push the tag**

```bash
git tag -a v0.1.0 -m "v0.1.0 — initial release"
git push origin v0.1.0
```

Marks the project as having shipped a usable v1.

---

## Self-Review

Per the writing-plans skill, this was reviewed against the spec inline. Findings:

**Spec coverage check:**

- ✅ Engine = docling, CPU mode → Task 4 (`_make_converter`)
- ✅ Single-PDF + batch CLI modes → Tasks 11 (single), 7 + 11 (batch)
- ✅ Self-contained per-PDF output folder → Task 4 (output layout)
- ✅ `pdfs/` → `outputs/` defaults, `--in`/`--out` overrides → Tasks 1 (.gitignore + .gitkeep), 10 (CLI flags), 11 (resolution)
- ✅ OCR on by default, ACCURATE table mode → Task 4 (`_make_converter`)
- ✅ `--fast`, `--no-images`, `--force`, `--strict`, `--verbose`, `--version`, `--help` → Tasks 10 (parser), 11 (wiring)
- ✅ Provenance header (source, pages, extractor) → Task 5
- ✅ Deterministic outputs (no timestamp) → Task 5 (test asserts byte-identical re-run)
- ✅ Skip-existing + `--force` → Task 8
- ✅ Per-PDF error isolation, `--strict` opt-in fail-fast → Task 9
- ✅ Per-PDF log lines + final summary + exit codes (0/1/2) → Task 11
- ✅ MIT license → Task 1
- ✅ pyproject.toml with `pdf2md` console script → Task 1
- ✅ Tests with pytest + tiny fixture → Tasks 2, 3–11
- ✅ GitHub Actions CI → Task 13
- ✅ README → Task 12
- ✅ `.gitignore` keeps user PDFs/outputs out of git → Task 1
- ✅ Page anchors deferred to v2 (per spec amendment) → not in any task; documented in README limitations
- ✅ `_artifacts/` folder naming (per spec amendment) → README + tests reflect this

**Placeholder scan:** none found. Every task has complete code blocks and exact commands.

**Type consistency:**
- `ConversionResult` defined in Task 3, used in Tasks 4, 7, 8, 9, 11. Field names consistent throughout.
- `BatchSummary` defined in Task 3, used in Task 7, 11. Consistent.
- `ConversionStatus.SUCCESS/SKIPPED/FAILED` defined in Task 3, used in Tasks 4, 7, 8, 9, 11. Consistent.
- `convert_one(source, output_root, *, fast_tables, with_images)` — signature matches between definition (Task 4) and callers (Task 7's `convert_batch`, Task 11's CLI).
- `convert_batch(in_dir, out_dir, *, force, strict, fast_tables, with_images, on_progress)` — signature matches between definition (Task 7, extended Tasks 8, 9) and Task 11's CLI call.
- `build_parser()` and `main(argv)` defined in Task 10, extended in Task 11. Consistent.

No issues to fix.

---

## Execution notes

- **Test runtime:** convert tests do real PDF conversion via docling. First run after install may take 1–3 minutes (model downloads); subsequent runs ~30–90s per test. Consider a `pytest -k` filter when iterating.
- **OMP_NUM_THREADS:** spec mentions docling's `num_threads=4` default. Tasks bake this in. To override at runtime: `OMP_NUM_THREADS=8 pdf2md ...` (env var, not a CLI flag).
- **Docling API stability:** if the docling API has shifted by the time this plan executes, the call sites in Tasks 4–6 may need adjusting. The verification in Task 1 step 9 will catch any install-time API breakage; test failures in Task 4 would catch API call breakage.
- **Sample PDF regeneration:** if `tests/fixtures/sample.pdf` is ever lost or needs editing, the steps in Task 2 (install reportlab + run the heredoc + uninstall reportlab) regenerate it.
