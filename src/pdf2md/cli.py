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
