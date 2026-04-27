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
