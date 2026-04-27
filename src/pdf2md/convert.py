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
