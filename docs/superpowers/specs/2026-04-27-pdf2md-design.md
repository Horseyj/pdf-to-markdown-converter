# pdf2md — Design Spec

**Date:** 2026-04-27
**Status:** Approved (design phase). Implementation plan to be written next.
**Owner:** James H

---

## Goal

A lean, high-quality, single-purpose Python utility that converts arbitrary PDFs (clean digital, scanned, hairy real-world educational/guide content) into clean markdown that humans and LLMs can read or write against.

**v1 audience:** the owner. Convert ~15 educational/guide PDFs (2–150 pages each) to markdown for downstream LLM and authoring workflows.

**v2+ audience:** anyone on the public internet who needs PDF → markdown. The repo is structured from day one for eventual public release on GitHub and PyPI, but is not held to public-quality bar (extensive docs, contributor onboarding, broad PDF-type test matrix) until v2.

---

## Non-goals (v1)

- Multi-backend routing (e.g., pymupdf4llm for clean PDFs + docling for hairy ones)
- GUI or web interface
- Configuration files (CLI flags + sane defaults are sufficient)
- Concurrent multi-PDF conversion (sequential is simpler and good enough overnight)
- Resume mid-PDF (file-level skip-existing is sufficient)
- Other input formats (DOCX, PPTX, EPUB) — name says `pdf2md`
- Python <3.10 support — docling's own minimum is 3.10, so we match it. Originally specced 3.11 floor; lowered during implementation because the dev machine ships 3.10 and the 3.11 features the project would use are nil.
- Public-quality test matrix across diverse PDF types

These are explicitly out of scope. Do not build them.

---

## Architecture

Single Python package, one conversion engine, one CLI entry point with two run modes.

- **Package name:** `pdf2md`
- **Engine:** [docling](https://github.com/docling-project/docling) (IBM Research). CPU mode. Chosen because it is the only mature single-backend option that handles hairy PDFs (OCR, complex layout, tables) acceptably on CPU. Marker is higher quality on book-like content but requires a GPU for tolerable speed; pymupdf4llm is fast but weak on hairy PDFs; MinerU is GPU-recommended.
- **Distribution:** real installable package via `pyproject.toml`. Installed with `pip install -e .` from source (eventually `pip install pdf2md` from PyPI). Provides a `pdf2md` console-script entry point usable from any directory.

### Run modes

| Invocation | Behavior |
|---|---|
| `pdf2md` | Batch mode using defaults: read `./pdfs/`, write `./outputs/` |
| `pdf2md path/to/file.pdf` | Single-PDF mode, write to `./outputs/<stem>/<stem>.md` |
| `pdf2md --in DIR --out DIR` | Batch with custom input/output directories |
| `pdf2md path/to/file.pdf --out DIR` | Single PDF with custom output directory |
| `python -m pdf2md ...` | Equivalent to `pdf2md ...` (works without install) |

---

## Repo Layout

```
pdf-to-md-converter/
├── README.md                    # what it does, install, usage, limitations, engine credit
├── LICENSE                      # MIT
├── pyproject.toml               # package metadata, deps, entry point
├── Makefile                     # `make install`, `make test`, `make convert`
├── .gitignore                   # ignores pdfs/* outputs/* Python cruft .venv
├── pdfs/.gitkeep                # default input drop folder (contents gitignored)
├── outputs/.gitkeep             # default output land folder (contents gitignored)
├── src/pdf2md/
│   ├── __init__.py              # version export
│   ├── __main__.py              # enables `python -m pdf2md`
│   ├── cli.py                   # argparse + entry point (delegates to convert.py)
│   └── convert.py               # convert_one() + convert_batch()
├── tests/
│   ├── fixtures/sample.pdf      # tiny public-domain PDF (≤2 pages) for CI
│   └── test_convert.py          # unit + smoke tests
├── docs/superpowers/specs/      # this design + future specs
├── docs/superpowers/plans/      # implementation plans
└── .github/workflows/test.yml   # run pytest on push
```

**File size principle:** prefer small focused files. `cli.py` and `convert.py` each have one clear responsibility. If either grows past ~200 lines, split it.

---

## Conversion Behavior

### Per-PDF output structure

```
outputs/<pdf-stem>/
├── <pdf-stem>.md                    # markdown body
└── <pdf-stem>_artifacts/            # all extracted images (if any)
    ├── image_000000_<hash>.png
    ├── image_000001_<hash>.png
    └── ...
```

The output folder is **self-contained** — copy/zip/ship the folder and image links resolve correctly. The `_artifacts/` suffix and image filenames inside it are the docling library's convention (`ImageRefMode.REFERENCED`); we accept it rather than post-processing the output to rename files and rewrite markdown image links.

### Markdown header

Each output `.md` begins with provenance comments (HTML comments, invisible in rendered markdown):

```markdown
<!-- source: <original-filename>.pdf -->
<!-- pages: <N> -->
<!-- extractor: docling <version> -->
```

**No timestamp.** Outputs must be deterministic across re-runs (same input → byte-identical output) so they are diffable in git.

### Page anchors (deferred to v2)

The `fr_technical_module` repo's `pdf_extract.py` inserted `<!-- page N -->` anchors between page chunks (a feature of the `pymupdf4llm` extractor). Docling's default markdown export does not emit these. Implementing them requires a custom `MarkdownDocSerializer` subclass that walks the document item-by-item and emits a comment whenever `item.prov[0].page_no` changes. This is non-trivial code that does not block the core "PDF → clean markdown" goal. Deferred to v2.

### Image references

Images extracted from the PDF are written to `exhibits/` as PNG. The markdown references them via paths **relative to the markdown file's own directory** (e.g., `exhibits/img-001.png`), so the file renders correctly when opened from any location.

### Engine settings

- **OCR:** on by default. v1 input is described as "hairy" educational/guide PDFs; some pages may be scanned or image-only. Docling's OCR (Tesseract or RapidOCR backend, whichever docling defaults to in current version) handles these.
- **Tables:** `TableFormerMode.ACCURATE` by default. Quality > speed for v1 use case. `--fast` flag overrides to `TableFormerMode.FAST`.
- **Image extraction:** enabled by default. `--no-images` flag disables (markdown-only output, no `exhibits/` folder).
- **Threads:** docling default (`OMP_NUM_THREADS=4`). Configurable via env var, not CLI flag (advanced use).

---

## CLI Surface

### Arguments

```
pdf2md [INPUT] [options]

Positional:
  INPUT           Path to a single PDF (single-PDF mode) or a directory
                  (batch mode, equivalent to --in DIR). Omit for batch mode
                  using the default --in (./pdfs).

Options:
  --in DIR        Batch input directory (default: ./pdfs)
  --out DIR       Output directory (default: ./outputs)
  --force         Re-convert even if output already exists
  --fast          Use FAST table mode instead of ACCURATE
  --no-images     Skip image extraction
  --strict        Fail-fast on first error (for CI)
  -v, --verbose   Verbose logging
  --version       Print version and exit
  -h, --help      Show help
```

### Resolution rules

- If `INPUT` is given and is a `.pdf` file → single-PDF mode
- If `INPUT` is given and is a directory → equivalent to `--in <dir>`
- If `INPUT` is omitted → batch mode, `--in` (or default `./pdfs`)
- `--out` always specifies the output root directory; per-PDF subfolders are created inside it

### Examples

```bash
# Batch, defaults (read ./pdfs, write ./outputs)
pdf2md

# Batch, custom paths
pdf2md --in ~/Documents/MyPDFs --out ~/Desktop/Converted

# Single PDF
pdf2md ~/Downloads/handbook.pdf

# Single PDF with custom output
pdf2md ~/Downloads/handbook.pdf --out ~/Desktop/Converted

# Re-convert everything (overwrite)
pdf2md --force
```

---

## Batch Behavior + Error Handling

### Discovery

- Walks `--in` **non-recursively** for `*.pdf` (case-insensitive).
- Recursive walk is a possible v2 flag (`--recursive`), not v1.

### Skip-existing

- For each input `foo.pdf`, the conversion is **skipped** if `<out>/foo/foo.md` already exists.
- `--force` overrides skip and re-converts.
- Skipped files still appear in the final summary and exit-code calculation.

### Per-PDF error isolation

- Each PDF conversion is wrapped in try/except.
- A failure on one PDF logs the error and **continues** to the next.
- Without `--strict`: batch processes every PDF before exiting.
- With `--strict`: batch aborts on the first failure (useful in CI).

### Progress display

Simple per-PDF log lines, one per file:

```
[1/15] handbook.pdf → outputs/handbook/ (47s, 89 pages)
[2/15] guide.pdf → outputs/guide/ (12s, 22 pages)
[3/15] SKIP corrupted.pdf (output exists, use --force to overwrite)
[4/15] FAILED scanned-bad.pdf: <error message>
```

No fancy progress bars. Stdout is the log; stderr is for errors.

### Final summary

Always printed at end of batch:

```
12 succeeded, 2 failed, 1 skipped
Total time: 14m 32s
Output: ./outputs/
```

### Exit codes

- `0` — all PDFs succeeded or were skipped
- `1` — one or more PDFs failed
- `2` — invocation error (bad arguments, missing input directory)

---

## Public-Ready Posture

### License

**MIT.** Standard, permissive, expected for a public Python utility. Single `LICENSE` file in repo root.

### README

Includes:
1. **One-line description**
2. **Install** — copy-pasteable command (one for default, one for CPU-only PyTorch wheels)
3. **Quickstart** — single-PDF example, batch example
4. **CLI reference** — all flags
5. **Supported PDF types** — clean digital, scanned (via OCR), tables, images
6. **Limitations** — complex math/equations may need manual review; very large PDFs (500+ pages) take a long time on CPU; not optimized for forms or non-Latin scripts
7. **Engine credit** — "Built on [docling](https://github.com/docling-project/docling) by IBM Research"
8. **License** — MIT

No emojis. No "features" marketing fluff.

### Tests

- **Framework:** pytest
- **Fixture:** one tiny (≤2 page) public-domain PDF in `tests/fixtures/sample.pdf`. Source it from project Gutenberg, a federal-government document, or generate one with reportlab. Must be redistributable.
- **Coverage:**
  - `test_convert_one_produces_expected_structure` — output folder, .md file, exhibits/ folder, header comments present
  - `test_convert_one_deterministic` — re-running on same input produces byte-identical .md
  - `test_convert_batch_skips_existing` — second run with same inputs skips all
  - `test_convert_batch_force_overrides_skip` — `--force` re-converts
  - `test_convert_batch_isolates_errors` — one bad PDF in a batch doesn't abort the rest
  - `test_cli_argument_parsing` — argparse correctness (invalid args fail cleanly)
  - `test_cli_smoke_single_pdf` — end-to-end: invoke CLI on fixture, assert output exists

### CI

GitHub Actions workflow at `.github/workflows/test.yml`:
- Runs on push to any branch
- Python 3.10, 3.11, and 3.12 matrix
- Install deps, run `pytest`
- Fail on test failures

### .gitignore

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

### Dependency posture

- `pyproject.toml` lists docling with a major-version floor (e.g., `docling>=2,<3`). No tight pinning beyond that — public users get fresh versions.
- **CPU PyTorch wheels:** docling brings PyTorch as a transitive dep. Default `pip install -e .` will pull GPU wheels (~2GB). For CPU-only systems, README documents the alternative install: `pip install -e . --extra-index-url https://download.pytorch.org/whl/cpu` (~200MB). The `Makefile` provides `make install` that runs the CPU-wheels variant by default.

---

## Open questions / decisions deferred to implementation

- **Sample PDF source.** Need to pick one that is unambiguously redistributable under MIT. Candidates: a short federal document (public domain in US), a project Gutenberg text re-rendered as PDF, or a generated one via reportlab. Decide during implementation.
- **Exact docling API call.** The library evolves; the implementation plan should query current docling docs (via context7 or pypi) to use the canonical API rather than guessing.
- **Whether `make install` should also create a venv.** Probably yes (`python3 -m venv .venv && .venv/bin/pip install ...`) for full reproducibility. Decide during implementation.

---

## Cross-cutting principles

- **Production-grade by the book.** Type hints throughout. No bare excepts. No print debugging left in. Functions do one thing. Files are small.
- **Determinism.** Same input always produces the same output. No timestamps, no random IDs, no nondeterministic ordering.
- **Lean.** No dependency added without justification. No abstraction added before it's needed. Two source files of real logic; expand only when forced to.
- **Public-ready structure, internal-quality v1 surface.** Repo shape, tests, CI, license, .gitignore are all set up for a public release. Documentation and edge-case coverage are sized for a single-user v1 and grow when v2 actually needs them.
