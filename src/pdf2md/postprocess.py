"""Post-extraction markdown cleanup.

docling produces accurate but noisy markdown for the kinds of mixed-layout
PDFs this tool targets. Three noise sources show up consistently:

1. **HTML entities** leak through (`&amp;`, `&gt;`, ...) instead of their
   decoded characters.
2. **Table of contents** is extracted as its own section, so every entry
   appears twice — once in the TOC, once at the real section later.
3. **Heading explosion** — docling's layout model classifies many paragraph
   fragments as h2s, polluting the section structure.

This module cleans all three. It operates on already-extracted markdown
text — pure ``str -> str`` (with stats), no I/O. The CLI/script layer is
responsible for reading and writing files.

Design notes:

* **Conservative by default.** When uncertain whether content is TOC noise
  or real prose, we leave it. When uncertain whether an h2 is a fragment,
  we *demote* it (strip the ``## ``) rather than delete — text survives.
* **Idempotent.** ``postprocess(postprocess(x)) == postprocess(x)``.
* **Pure functions.** No I/O. All thresholds are module-level constants.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field


# --- Tunable thresholds ------------------------------------------------------
#
# Bodies are compared to these limits to decide "is this real content or
# noise?" The numbers are deliberately generous so the heuristics fail toward
# "leave it alone" rather than "delete it." See the brief for the corpus
# evidence behind each choice.

MAX_HEADING_CHARS = 120
"""Headings longer than this are paragraphs mis-tagged as h2 (subtype 3b)."""

LAYOUT_ARTIFACT_BODY_THRESHOLD = 50
"""An h2 whose body has fewer non-image text chars than this is a layout
artifact (subtype 3d) — covers both cover-page chrome and h2s whose content
was split into a following h2 by docling."""

PROSE_MIN_LINE_LEN = 200
"""A single body line at least this long is sentence-length prose — strong
signal the section is real content, not a TOC entry."""

PROSE_PARAGRAPH_MIN_LEN = 80
"""A non-list, non-image body line at least this long counts as a paragraph.
Distinguishes real content (which mixes paragraphs with bullets) from TOC
sub-entries (which are bullets-only or short-fragment-only)."""

PROSE_TOTAL_CHARS_THRESHOLD = 800
"""A body with at least this many non-image chars across multiple lines is
substantial content even without a single long line — catches all-bullet
sections like a long checklist."""

PROSE_MIN_BODY_LINES = 3
"""Companion to PROSE_TOTAL_CHARS_THRESHOLD."""


# --- Regexes -----------------------------------------------------------------

_H2_RE = re.compile(r"^##\s+(?!#)(.*?)\s*$")
"""Match exactly an h2 (`## ...`), not h3+. Group 1 is the heading text."""

_IMAGE_LINE_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$")
"""Match a line whose only content is a markdown image reference."""

_LIST_LINE_RE = re.compile(r"^\s*(?:[-*+]\s|\d+[.\)]\s)")
"""Match a bullet or numbered list line (or a list-task line like `- [x]`)."""

_BLOCKQUOTE_RE = re.compile(r"^\s*>\s")

_CODE_FENCE_RE = re.compile(r"^\s*```")

_TABLE_RE = re.compile(r"^\s*\|")

_ENTITY_RE = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);")
"""Match named, decimal, and hex HTML entities for counting purposes."""

_TOC_HEADING_RE = re.compile(
    r"^##\s+(?:table\s+of\s+contents|contents)\s*$",
    re.IGNORECASE,
)
"""Match `## Contents` or `## Table of Contents` (case-insensitive)."""


# --- Stats -------------------------------------------------------------------


@dataclass
class PostprocessStats:
    """Counts of what each pass did. Used for batch-mode summaries and tests."""

    entities_decoded: int = 0
    toc_regions_removed: int = 0
    headings_demoted_ellipsis: int = 0
    headings_demoted_overlong: int = 0
    headings_demoted_label: int = 0
    headings_demoted_layout: int = 0

    @property
    def total_headings_demoted(self) -> int:
        return (
            self.headings_demoted_ellipsis
            + self.headings_demoted_overlong
            + self.headings_demoted_label
            + self.headings_demoted_layout
        )

    def summary(self) -> str:
        """One-line, batch-friendly summary."""
        parts = []
        if self.toc_regions_removed:
            parts.append(f"TOC removed ({self.toc_regions_removed} region)")
        if self.total_headings_demoted:
            parts.append(f"{self.total_headings_demoted} headings demoted")
        if self.entities_decoded:
            parts.append(f"{self.entities_decoded} entities decoded")
        return ", ".join(parts) if parts else "no changes"


# --- Pass 1: HTML entities ---------------------------------------------------


def decode_html_entities(text: str) -> tuple[str, int]:
    """Decode HTML entities (``&amp;``, ``&gt;``, ``&#39;`` etc.) to characters.

    docling emits these entities raw in the markdown body. Using
    :func:`html.unescape` rather than a hand-rolled replace chain ensures we
    cover entities we haven't seen yet (e.g. ``&hellip;``, ``&ldquo;``).

    Example: ``Firm- &amp; Role-specific`` → ``Firm- & Role-specific``.

    Idempotent: a second pass is a no-op because the first pass produces
    text with no remaining entities.
    """
    count = len(_ENTITY_RE.findall(text))
    return html.unescape(text), count


# --- Pass 2: TOC region removal ----------------------------------------------


def _body_lines(lines: list[str], start: int, end: int) -> list[str]:
    """Lines [start, end). The caller has already excluded the heading line
    itself by passing start = heading_idx + 1."""
    return lines[start:end]


def _has_prose_body(body: list[str]) -> bool:
    """Decide whether an h2's body is real content.

    True if any of the documented prose signals fire. Errs toward True
    (under-cleaning) — see module docstring on why we'd rather leave noise
    than delete real content.
    """
    # Strip blank lines and image-only lines — those don't count as content.
    non_blank = [ln for ln in body if ln.strip()]
    non_image = [ln for ln in non_blank if not _IMAGE_LINE_RE.match(ln)]
    if not non_image:
        return False

    # 1. A sentence-length single line.
    if any(len(ln.strip()) >= PROSE_MIN_LINE_LEN for ln in non_image):
        return True

    # 2. Code or blockquote — never appear in TOCs.
    if any(_CODE_FENCE_RE.match(ln) for ln in non_image):
        return True
    if any(_BLOCKQUOTE_RE.match(ln) for ln in non_image):
        return True

    # 3. Substantial body — lots of content even without one long line.
    total = sum(len(ln.strip()) for ln in non_image)
    if total > PROSE_TOTAL_CHARS_THRESHOLD and len(non_image) > PROSE_MIN_BODY_LINES:
        return True

    # 4. A paragraph-style line (not list/table/heading/image) at least
    # PROSE_PARAGRAPH_MIN_LEN chars. This is the signal that distinguishes
    # TMAY Compendium's real "## Walk Me Through Your Resume" section
    # (which mixes a 120-char quoted line with short bullets) from
    # "Why This Role Bible"'s TOC sub-entries (which are bullets-only,
    # all under 80 chars each).
    for ln in non_image:
        s = ln.strip()
        if _LIST_LINE_RE.match(ln) or _TABLE_RE.match(ln):
            continue
        if s.startswith("#") or s.startswith(">"):
            continue
        if len(s) >= PROSE_PARAGRAPH_MIN_LEN:
            return True

    return False


def _find_h2_indices(lines: list[str]) -> list[int]:
    """Indices of every h2 line. Excludes h3+ (matches exactly `## `)."""
    return [i for i, ln in enumerate(lines) if _H2_RE.match(ln)]


def remove_toc_region(text: str) -> tuple[str, int]:
    """Delete the TOC region from a document, conservatively.

    The TOC region runs from the first ``## Contents`` (or
    ``## Table of Contents``) heading up to — but not including — the first
    following h2 whose body is prose-like. If no following prose-h2 exists,
    we leave the document untouched (see :func:`_has_prose_body` for the
    prose criteria).

    Returns ``(text, n_regions_removed)`` — 0 if nothing was removed, 1 if
    a region was removed. Only the first Contents heading is considered;
    duplicate Contents headings later in the document are left for the
    fragment-heading pass to handle.

    Example: in a "TMAY Compendium"-style doc, this removes ``## Contents``
    plus all the orphan-h2 TOC sub-entries up to the real first section.
    """
    lines = text.splitlines(keepends=False)
    if not lines:
        return text, 0

    # Find first TOC heading.
    toc_idx = next(
        (i for i, ln in enumerate(lines) if _TOC_HEADING_RE.match(ln)),
        None,
    )
    if toc_idx is None:
        return text, 0

    # Walk forward through subsequent h2s until we find one with prose body.
    h2_indices = [i for i in _find_h2_indices(lines) if i > toc_idx]
    if not h2_indices:
        # `## Contents` is the only h2 — unusual layout, leave untouched.
        return text, 0

    first_prose_h2: int | None = None
    for k, h2_idx in enumerate(h2_indices):
        body_end = h2_indices[k + 1] if k + 1 < len(h2_indices) else len(lines)
        body = _body_lines(lines, h2_idx + 1, body_end)
        if _has_prose_body(body):
            first_prose_h2 = h2_idx
            break

    if first_prose_h2 is None:
        # No prose section found anywhere after Contents — conservative
        # default per brief: leave document alone.
        return text, 0

    # Delete [toc_idx, first_prose_h2). Preserve trailing newline shape.
    kept = lines[:toc_idx] + lines[first_prose_h2:]
    trailing_nl = text.endswith("\n")
    out = "\n".join(kept) + ("\n" if trailing_nl else "")
    return out, 1


# --- Pass 3: fragment-heading demotion ---------------------------------------


def _ends_with_ellipsis(heading_text: str) -> bool:
    s = heading_text.rstrip()
    return s.endswith("…") or s.endswith("...")


def _is_label_form(heading_text: str, body: list[str]) -> bool:
    """Heading ends with ``:``, body's first non-blank line is a list item.

    The list signal matters — a colon-terminated heading followed by prose
    is usually a legitimate heading; followed by a list it's a paragraph
    lead-in that docling mis-tagged.
    """
    if not heading_text.rstrip().endswith(":"):
        return False
    for ln in body:
        if not ln.strip():
            continue
        if _IMAGE_LINE_RE.match(ln):
            continue
        return bool(_LIST_LINE_RE.match(ln))
    return False


def _is_layout_artifact(body: list[str]) -> bool:
    """Body is essentially empty after excluding images and blank lines.

    Catches three things: cover-page chrome with no content under it,
    h2s whose content was hoisted into a following h2 by docling's
    layout model, and short-fragment list-of-section-names entries
    that escaped the TOC pass.
    """
    non_blank = [ln for ln in body if ln.strip()]
    non_image = [ln for ln in non_blank if not _IMAGE_LINE_RE.match(ln)]
    total_chars = sum(len(ln.strip()) for ln in non_image)
    return total_chars < LAYOUT_ARTIFACT_BODY_THRESHOLD


def demote_fragment_headings(text: str) -> tuple[str, dict[str, int]]:
    """Demote h2s that look like paragraph fragments to plain paragraph lines.

    Five documented subtypes (see brief):

    * **3a ellipsis**  — heading ends with `…` or `...`. Sentence lead-in
      to a bullet list, e.g. ``## Behavioral Questions evaluate a candidate's…``
    * **3b overlong**  — heading text > MAX_HEADING_CHARS. Paragraph
      mis-tagged as a title.
    * **3c label**     — ends with `:`, body's first non-blank line is a
      list item. E.g. ``## Strong reasons to include:`` followed by bullets.
    * **3d layout**    — body has < LAYOUT_ARTIFACT_BODY_THRESHOLD chars
      after excluding images. Covers both empty h2s ("## Why this City?"
      with no body because the next h2 follows immediately) and cover-page
      chrome.
    * **3e cover chrome** — caught by 3d, no separate rule.

    Demotion strips the ``## `` prefix. The text survives as a paragraph,
    so retrieval-time downstream consumers still see it; it just stops
    anchoring a section in the manifest.

    Returns ``(text, counts_by_subtype)``.
    """
    lines = text.splitlines(keepends=False)
    counts = {
        "ellipsis": 0,
        "overlong": 0,
        "label": 0,
        "layout": 0,
    }
    if not lines:
        return text, counts

    h2_indices = _find_h2_indices(lines)
    if not h2_indices:
        return text, counts

    # Decide per-h2 which to demote. Use a list of (idx, new_line) edits.
    # We iterate in one pass using the original h2_indices, so the body of
    # each h2 is computed against the unmodified document — keeps the logic
    # straightforward and the result deterministic.
    edits: dict[int, str] = {}
    for k, h2_idx in enumerate(h2_indices):
        m = _H2_RE.match(lines[h2_idx])
        if not m:
            continue
        heading_text = m.group(1)
        body_end = h2_indices[k + 1] if k + 1 < len(h2_indices) else len(lines)
        body = _body_lines(lines, h2_idx + 1, body_end)

        # Order of checks matters for stats accounting only — a heading is
        # demoted once. We attribute it to the FIRST matching subtype, in
        # the order documented in the brief.
        subtype: str | None = None
        if _ends_with_ellipsis(heading_text):
            subtype = "ellipsis"
        elif len(heading_text) > MAX_HEADING_CHARS:
            subtype = "overlong"
        elif _is_label_form(heading_text, body):
            subtype = "label"
        elif _is_layout_artifact(body):
            subtype = "layout"

        if subtype is not None:
            edits[h2_idx] = heading_text
            counts[subtype] += 1

    if not edits:
        return text, counts

    new_lines = [edits.get(i, ln) for i, ln in enumerate(lines)]
    trailing_nl = text.endswith("\n")
    out = "\n".join(new_lines) + ("\n" if trailing_nl else "")
    return out, counts


# --- Top-level chain ---------------------------------------------------------


def postprocess(text: str) -> tuple[str, PostprocessStats]:
    """Run all three cleanup passes in order. Pure function; returns stats.

    Order: entity decode -> TOC removal -> fragment-heading demotion.
    Entity decode runs first so downstream heuristics see clean text
    (e.g. ``## Common Questions & Answers`` matches as a 28-char body
    rather than 33).
    """
    stats = PostprocessStats()

    text, stats.entities_decoded = decode_html_entities(text)
    text, stats.toc_regions_removed = remove_toc_region(text)
    text, subtype_counts = demote_fragment_headings(text)
    stats.headings_demoted_ellipsis = subtype_counts["ellipsis"]
    stats.headings_demoted_overlong = subtype_counts["overlong"]
    stats.headings_demoted_label = subtype_counts["label"]
    stats.headings_demoted_layout = subtype_counts["layout"]

    return text, stats
