# pdf2md

Convert PDFs to clean markdown using [docling](https://github.com/docling-project/docling). Single command, batch and single-PDF modes, self-contained per-PDF output. Handles digital PDFs, scanned PDFs (OCR), and complex layouts (tables, images).

## Should you use this?

There are a lot of PDF→markdown tools. Here's an honest read on when `pdf2md` is the right one — and when it isn't.

**Use `pdf2md` if you:**

- **Run on CPU only** (laptop, no NVIDIA GPU). Most engines that match docling's quality need a GPU for tolerable speed. `pdf2md` does ~3–4 seconds per page on a typical CPU. For comparison, `marker` runs ~16 seconds per page on the same hardware — a 50-page PDF takes 13+ minutes there versus ~3 minutes here.
- **Convert many PDFs unattended.** Drop a folder, run one command, walk away. Skip-existing means re-runs are cheap; per-PDF error isolation means one bad file doesn't kill the batch.
- **Care about table fidelity.** docling's TableFormer preserves merged cells and nested headers that lighter engines flatten. For training material, financial reports, or research papers with real tables, this matters more than it first sounds.
- **Want everything to stay local.** Your PDFs never leave your machine. Free, no quota, no upload, no privacy-policy reading required.
- **Want deterministic output.** The same input always produces a byte-identical `.md`. Outputs are diffable in git, which makes downstream pipelines (review, RAG ingestion, content QA) much easier to reason about.
- **Need a real CLI you can script.** Not a browser upload, not a hosted form — a single command with flags, exit codes, and a progress log.

**Use something else if you:**

- **Want the highest possible quality and you have a GPU** (or are willing to rent one). [`marker`](https://github.com/datalab-to/marker) is slightly stronger on prose-heavy book content. The catch is its CPU performance — without a GPU, you'll wait hours for what `pdf2md` finishes in minutes. If you have a GPU, marker is a serious contender.
- **Need state-of-the-art accuracy on math, scientific notation, or non-Latin scripts** and are okay with a paid hosted API. [Mistral OCR](https://mistral.ai/news/mistral-ocr) is excellent at these. Cloud-only and metered, but the quality on hard content is currently best-in-class.
- **Just need a one-off browser conversion** and don't want to install anything. A hosted SaaS is the right shape for that. We don't recommend a specific one — most are opaque about pricing, the engine they use, and their privacy practices.
- **Have only clean, born-digital PDFs** (no scanned pages, no complex layout) and want maximum speed at minimum install cost. [`pymupdf4llm`](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/) is faster and lighter when you don't need OCR. It's the right tool for clean inputs; it's the wrong tool for hairy ones.

**What `pdf2md` actually adds.** This is a thin wrapper. Most of the credit goes to docling for the conversion. What's on top: a CLI tuned for batch use, sensible defaults for messy real-world PDFs (OCR on, accurate table mode), per-PDF self-contained output folders, deterministic markdown headers for traceability, skip-existing and `--force`, per-PDF error isolation with a `--strict` opt-in, MIT license, no telemetry, no account required.

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
