"""Command-line interface for pdf2md."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pdf2md import __version__
from pdf2md.convert import (
    BatchSummary,
    ConversionResult,
    ConversionStatus,
    convert_batch,
    convert_one,
)
from pdf2md.postprocess import postprocess


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
    parser.add_argument(
        "--postprocess-only",
        metavar="PATH",
        help=(
            "Skip PDF conversion; re-run the markdown postprocessing pass on "
            "an existing .md file or directory (walked recursively for *.md). "
            "Files are rewritten in place."
        ),
    )
    parser.add_argument("--version", action="version", version=f"pdf2md {__version__}")
    return parser


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


def _run_postprocess_only(path: Path) -> int:
    """Re-run the postprocess pass over a .md file or a directory of .md files.

    Files are rewritten in place. Returns the CLI exit code (0 success,
    2 invocation error).
    """
    if not path.exists():
        print(f"pdf2md: path not found: {path}", file=sys.stderr)
        return 2

    if path.is_file():
        targets = [path]
    else:
        targets = sorted(path.rglob("*.md"))

    if not targets:
        print(f"pdf2md: no .md files found at {path}", file=sys.stderr)
        return 2

    for md in targets:
        new_text, stats = postprocess(md.read_text())
        md.write_text(new_text)
        print(f"{md.name}: {stats.summary()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.postprocess_only:
        return _run_postprocess_only(Path(args.postprocess_only))

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
