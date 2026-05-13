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
    from pdf2md import __version__

    r = run_cli("--version")
    assert r.returncode == 0
    assert "pdf2md" in r.stdout
    assert __version__ in r.stdout


def test_cli_help():
    r = run_cli("--help")
    assert r.returncode == 0
    assert "pdf2md" in r.stdout
    assert "--in" in r.stdout
    assert "--out" in r.stdout
    assert "--force" in r.stdout
    assert "--strict" in r.stdout


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


def test_cli_postprocess_only_on_single_file(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text(
        "## Contents\n\n"
        "## Orphan\n\n"
        "## Real\n\n"
        + ("Long paragraph content. " * 12)
        + "\n"
    )

    r = run_cli("--postprocess-only", str(md))
    assert r.returncode == 0, r.stderr
    out = md.read_text()
    assert "## Contents" not in out
    assert "## Real" in out
    assert "doc.md" in r.stdout


def test_cli_postprocess_only_on_directory(tmp_path):
    (tmp_path / "a.md").write_text("Body with &amp; entity. " * 20)
    (tmp_path / "b.md").write_text("Body with &gt; entity. " * 20)
    (tmp_path / "ignore.txt").write_text("not markdown")

    r = run_cli("--postprocess-only", str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "&amp;" not in (tmp_path / "a.md").read_text()
    assert "&gt;" not in (tmp_path / "b.md").read_text()
    # .txt file untouched.
    assert (tmp_path / "ignore.txt").read_text() == "not markdown"


def test_cli_postprocess_only_path_missing(tmp_path):
    r = run_cli("--postprocess-only", str(tmp_path / "nope"))
    assert r.returncode == 2
