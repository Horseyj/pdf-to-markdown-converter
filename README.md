# pdf2md

Convert PDFs to clean markdown using [docling](https://github.com/docling-project/docling). Single command, batch and single-PDF modes, self-contained per-PDF output. Handles digital PDFs, scanned PDFs (OCR), and complex layouts (tables, images).

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
