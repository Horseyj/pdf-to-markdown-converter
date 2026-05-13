# pdf2md

Convert PDFs to clean markdown — locally, in batch, on a regular laptop. Wraps [docling](https://github.com/docling-project/docling) (IBM Research) with sensible defaults and a real CLI.

## What it preserves

- Headings, lists, paragraphs (full hierarchy)
- Tables with merged cells and nested headers (via docling's TableFormer)
- Images and diagrams (extracted as PNG, referenced from the markdown)
- Hyperlinks and footnotes
- Multi-column layouts
- Math notation
- Scanned pages (OCR runs automatically when needed)

## Should you use this?

**Use `pdf2md` if you:**

- Run on CPU only — no NVIDIA GPU
- Need to convert many PDFs unattended (drop folder, walk away)
- Care about real table fidelity (merged cells, nested headers)
- Want everything local — no upload, no quota, no privacy policy to read
- Want deterministic output — same input always produces a byte-identical `.md`
- Want a real CLI with flags, exit codes, and a progress log

**Use something else if you:**

- **Have a GPU and want max quality on prose** → [marker](https://github.com/datalab-to/marker). Slightly stronger on book content. CPU is hours-vs-minutes worse than docling, so this only makes sense with GPU access.
- **Want best-in-class accuracy on math or non-Latin scripts** and a paid hosted API is fine → [Mistral OCR](https://mistral.ai/news/mistral-ocr). Cloud-only, metered, excellent on hard content.
- **Have only clean, born-digital PDFs and want max CPU speed** → [pymupdf4llm](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/) or [pdfmd](https://github.com/M1ck4/pdfmd). PyMuPDF-based, faster on simple content, weaker on complex tables.
- **Just need a one-off browser conversion** and don't want to install anything → any hosted SaaS will do. We don't endorse a specific one; most are opaque about pricing, engine, and data handling.

**What `pdf2md` adds.** A thin wrapper on docling. What's on top: a batch-tuned CLI with skip-existing, per-PDF error isolation, deterministic headers, sensible defaults for hairy real-world PDFs (OCR on, accurate table mode by default), MIT license, no telemetry, no account.

## Install

Requires Python 3.10 or newer.

```bash
git clone https://github.com/Horseyj/pdf-to-markdown-converter.git
cd pdf-to-markdown-converter
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
  --in DIR              Batch input directory (default: ./pdfs)
  --out DIR             Output directory (default: ./outputs)
  --force               Re-convert even if output already exists
  --fast                Use FAST table mode instead of ACCURATE (faster, less precise)
  --no-images           Skip image extraction
  --strict              Fail-fast on first error (for CI)
  --postprocess-only P  Re-run only the markdown post-processing pass on an
                        existing .md file or directory (rewrites in place)
  -v, --verbose         Verbose logging
  --version             Print version and exit
  -h, --help            Show help
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

### Content artifacts you may see

These are cosmetic — they don't degrade the document's information content and LLM consumers handle them fine — but humans skimming the markdown will notice:

- **Long dash-only lines** in PDFs that use comparison tables: docling renders empty cell borders as 60–130 character dash runs.
- **Renumbered lists** when the source PDF has multiple separate numbered lists in close proximity: docling sometimes merges them into one continuous sequence.
- **Letter-spacing collapse in headings** (e.g. `PROFESSIONALEXPERIENCE` or `P ROFES SION AL E X PERIENCE`): PDFs that style headings via per-character tracking lose word boundaries during text extraction.
- **OCR errors on bitmap-image pages** (scanned resumes, screenshots embedded in the PDF): single-character mistakes through to entirely garbled lines, depending on scan resolution. Born-digital text is unaffected.

## Markdown post-processing

Every conversion runs a post-processing pass over the extracted markdown to clean three noise patterns that docling consistently produces. The pass is pure text-in / text-out (it does not re-run extraction), idempotent, and conservative — when in doubt it leaves content alone rather than risk deletion.

**What it cleans:**

- **HTML entities** decoded via `html.unescape` — `&amp;`, `&gt;`, `&lt;`, `&quot;`, `&#39;`, `&nbsp;` and others become their characters.
- **Table-of-contents region** — when a `## Contents` (or `## Table of Contents`) heading is present, the TOC heading and the orphan h2 sub-entries that follow are deleted up to (but not including) the first h2 with prose-like body content. If no following prose section can be identified, the document is left untouched.
- **Heading-explosion fragments** — h2s that look like paragraph fragments are *demoted* (the `## ` prefix is stripped; the text survives as a paragraph). Five subtypes are caught: ellipsis-trailing sentence lead-ins, overlong headings (>120 chars), label-form headings (ending with `:` followed by a bullet/numbered list), layout-artifact h2s (body shorter than 50 non-image chars), and cover-page chrome (caught by the layout rule).

Demotion (rather than deletion) is the conservative default — if a heuristic fires on a real heading, the text is still present for human readers and downstream retrieval; only its role as a section anchor is removed.

### Re-running on already-extracted output

The post-processing pass also runs as a standalone command, so you can clean an existing `outputs/` tree without re-extracting PDFs (which is OCR-bound and slow). It rewrites files in place.

```bash
# Single file
pdf2md --postprocess-only outputs/MyDoc/MyDoc.md

# Directory — walked recursively for *.md files
pdf2md --postprocess-only outputs/
```

A one-line summary per file is printed to stdout, e.g. `MyDoc.md: TOC removed (1 region), 23 headings demoted, 41 entities decoded`.

## License

MIT. See `LICENSE`.

## Credits

Built on [docling](https://github.com/docling-project/docling) (IBM Research).
