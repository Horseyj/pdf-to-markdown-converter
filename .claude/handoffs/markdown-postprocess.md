# pdf2md post-processing pass for clean markdown extraction

**Task:** Add a post-processing pass to pdf2md that cleans the three noise sources docling leaves in extracted markdown — TOC duplication, heading explosion (paragraph fragments mis-tagged as h2), and HTML entity leaks — so the tool produces clean-enough markdown for downstream consumers. Build to production quality: generalizable across arbitrary PDFs, conservative by default, well-tested, observable, idempotent.

**Why this matters:** pdf2md is the upstream gate for all proprietary content the FR Consulting brain consumes. Today, the brain has 3 defensive band-aids (boilerplate blocklist, >120-char heading skip, <200-char content skip) papering over docling's noise. Cleaning at extraction time means those defenses can be removed AND any future PDF batch (operator's open-ended corpus expansion, eventual V2 video transcripts) benefits automatically. This tool will process many more docs over time — the bar is "works on any reasonable PDF-derived markdown," not "works on our 12 known files."

The brain-side stage (copy cleaned outputs, remove band-aids, rebuild manifest, regression test) happens AFTER this work merges. Out of scope here.

---

## The three noise sources (confirmed in the 12-file corpus)

### 1. HTML entity leak

docling emits `&amp;`, `&gt;`, `&lt;`, `&quot;`, `&apos;`, `&#39;`, `&nbsp;` raw in the markdown. Per-file occurrence counts in our corpus: 18 to 160.

Examples (real, copy-paste from `outputs/Behavioral_Handbook/`):
- `Firm- &amp; Role-specific Motivations`  → should be `Firm- & Role-specific Motivations`
- `M&amp;A transactions`  → should be `M&A transactions`
- `why them &gt; other candidates?`  → should be `why them > other candidates?`

**Cleanup:** Use Python stdlib `html.unescape()` for full coverage rather than a hand-rolled `.replace()` chain. Safer than a small custom list because docling may emit other entities we haven't observed yet. Apply across the entire markdown body.

### 2. Table of Contents (TOC) duplication

Every PDF has a "Contents" page. docling extracts it. It appears in one of two structural patterns:

**Pattern A — table-form TOC** (Behavioral Handbook style):
```
## Contents

| HOWTOUSETHISHANDBOOK                                          |
|---------------------------------------------------------------|
| BEHAVIORALCHEATSHEET                                          |
| TYPESOFBEHAVIORALQUESTIONS                                    |
| SIMPLEBEHAVIORALQUESTIONS Process (The 4-Step Framework) ...  |

## INVESTMENT BANKING LANDSCAPE QUESTIONS

Common Questions &amp; Answers

(then image)

## How to Use This Handbook

(real paragraph content starts here)
```

**Pattern B — orphan-h2-run TOC** (TMAY Compendium / Email Templates style):
```
## Contents

## WALK ME THROUGH YOUR RESUME

## GENERAL TMAYS

TMAY Example #1
TMAY Example #2
TMAY Example #3
...

## COVERAGE GROUP-SPECIFIC TMAYS

Technology Investment Banking Consumer Investment Banking

## PRODUCT GROUP-SPECIFIC TMAYS

(... several more orphan h2s with short list bodies ...)

## Walk Me Through Your Resume

(real bullet content + paragraphs start here)
```

In both patterns, the downstream router then sees every section name twice — once as a TOC entry, once as the real section later. Confuses retrieval.

**Cleanup approach:** Find the `## Contents` (or `## Table of Contents`) heading. Walk forward through h2 sections until reaching one with **prose-like body content**. Delete the range `[Contents heading, first-prose-heading)` — i.e. the Contents h2 itself plus all intermediate "TOC-looking" sections, but stop BEFORE the first real-section h2.

**What counts as "prose-like body"** (any one is enough):
- Any single line ≥ 200 chars (a sentence-length paragraph)
- A markdown bullet list with non-trivial bullet content
- A numbered list with content (`1.`, `2.`, ...)
- A fenced code block
- A blockquote
- Body has > 800 chars total across > 3 non-blank lines (substantial body even without long single lines)

**Conservative default:** if no prose-h2 is ever found after `## Contents` (unusual layout — possible on a brochure-style PDF), leave the document untouched. Better to under-clean than risk deleting real content. The brain's existing defenses can absorb noise; deleted real content is unrecoverable without re-running docling.

### 3. Heading explosion — paragraph fragments mis-tagged as h2

docling's layout model classifies a lot of paragraph fragments as h2. Five observed subtypes:

**3a. Ellipsis-trailing fragments** — sentence lead-ins to bullet lists. Example: `## Behavioral Questions evaluate a candidate's…` followed by 4 bullets.
- Pattern: heading ends in `…` (curly) or `...` (three dots).

**3b. Overlong headings** — paragraphs treated as titles. Threshold: > 120 chars.
- Heuristic kept for safety; in our corpus today this catches 0 entries (the brain band-aid is currently dormant), but defensively reasonable for future PDFs with different layout quirks.

**3c. Label-form headings** — h2 ending in `:` followed by a bullet/numbered list. Example: `## Strong reasons to include:` followed by 4 bullets.
- Pattern: heading ends with `:`, AND body's first non-blank line starts with `-`, `*`, or `<digit>.`.

**3d. Layout-artifact h2s** — h2 with body that's essentially empty (only images, blank lines, or < 50 chars of text). Example: `## Common Questions & Answers` with only an image below; `## Why this City?` with no body content because the next h2 follows immediately.
- Pattern: body text content (excluding image refs and blank lines) is < 50 chars.

**3e. Cover-page chrome** — h2s that are document titles or branding, typically with empty bodies.
- Examples: `## The Investment Banking Blueprint` (appears in all 12 docs), `## Behavioral Handbook` (the doc's own title appearing before Contents).
- These are caught by 3d (empty body) — no separate detection needed. **Do NOT hard-code a blocklist of known titles** ("The Investment Banking Blueprint" etc.) — the moment a non-Blueprint PDF arrives, that blocklist becomes wrong. The structural detection (empty body) generalizes.

**Cleanup action for all 5 subtypes: DEMOTE, do not delete.**

"Demote" = strip the `## ` prefix; the heading text stays in the document as a plain paragraph line. The content survives; it just stops anchoring a section.

Why demote rather than delete:
- Conservative — if the demotion is wrong, the text is still in the document for human readers and any downstream retrieval pass.
- Reversible during operator review — they can spot demoted text and re-promote if needed.
- Loses no signal — the brain's manifest builder won't index it as a section, which is the goal.

---

## Architecture

### Why a post-processing pass instead of fixing docling config

docling extraction is OCR-bound — minutes per PDF. The post-processing pass operates on the already-extracted .md text — pure functions, milliseconds to run. This decouples the slow extraction from the iteration loop on cleanup heuristics. (Same architectural insight that motivated the existing `_prune_repeated_images`.)

Bumping docling or changing `pipeline_options` is **not the right fix**: the TOC duplication isn't a docling bug — docling is correctly extracting the TOC page AND the real sections; the dedup is OUR responsibility. Similarly for heading-fragment mis-tagging, docling's layout model is doing what layout models do; the cleanup is downstream.

### Wire-in point

In `convert_one` after `_prune_repeated_images`:

```python
def convert_one(...):
    ...
    doc.save_as_markdown(out_md, ...)
    # prepend provenance header
    ...
    body = out_md.read_text()
    out_md.write_text(header + body)

    if with_images:
        _prune_repeated_images(out_md)

    # NEW: post-processing pass for TOC / fragment-headings / entities cleanup
    from pdf2md.postprocess import postprocess
    out_md.write_text(postprocess(out_md.read_text()))
    ...
```

### Standalone entry point for re-processing existing outputs

During iteration AND for future re-processing of an existing `outputs/` tree without re-extracting, expose an entry point. Two options — pick whichever you find cleaner:

- **Option A:** A new CLI flag `pdf2md --postprocess-only <path>` where `<path>` is either a single `.md` file or a directory walked for `.md` files. Reads → postprocesses → writes back.
- **Option B:** A separate `scripts/postprocess_existing.py` script invoked as `python -m scripts.postprocess_existing <path>` or `python scripts/postprocess_existing.py <path>`.

Document whichever you pick.

### Module structure

```
src/pdf2md/postprocess.py    # New module
  postprocess(text) -> tuple[str, PostprocessStats]   # Top-level chain
  decode_html_entities(text) -> str                   # Pass 1
  remove_toc_region(text) -> tuple[str, int]          # Pass 2: text + regions removed
  demote_fragment_headings(text) -> tuple[str, dict]  # Pass 3: text + counts by subtype
  PostprocessStats                                    # Dataclass for observability
```

Return values include stats so callers can observe what happened. The CLI/script entry point should print a summary line per file (e.g., `Behavioral_Handbook.md: TOC removed, 23 headings demoted, 41 entities decoded`).

---

## Gold-standard requirements

This is a tool that will run against unknown future PDFs. Build to that bar.

- **Pure functions throughout.** `text → text` (and `text → (text, stats)` where observability matters). No file I/O inside heuristics — easier to test, compose, reason about. File I/O belongs in the CLI/script layer and `convert.py`.
- **Conservative by default.** When unsure, demote (preserve content) rather than delete. Failure mode = leave noise. Not = lose content.
- **Configurable thresholds.** Body-length thresholds, heading char limit, etc. — expose as module-level constants (`MAX_HEADING_CHARS`, `LAYOUT_ARTIFACT_BODY_THRESHOLD`, `PROSE_MIN_LINE_LEN`, etc.). No magic numbers buried in regexes or function bodies.
- **Idempotent.** `postprocess(postprocess(x)) == postprocess(x)`. Test this explicitly.
- **Observable.** Return `PostprocessStats` reporting counts: TOC regions removed, headings demoted (broken down by subtype: ellipsis, overlong, label, layout-artifact), entities decoded. Print summary stats from the batch CLI/script. Inspired by `_prune_repeated_images` returning a count.
- **Documented heuristics.** Each heuristic function has a docstring explaining what fires it WITH a concrete example. Comment style consistent with existing `convert.py` — explain non-obvious WHY, not WHAT.
- **Tested.**
  - Unit tests per heuristic with inline-string fixtures (no PDF needed).
  - Edge cases covered: empty input, single line, no h2s at all, only h2s no body, TOC with no following prose-h2 (must leave unchanged), multiple `## Contents` headings (only first matters), ellipsis-only heading text, unicode-heavy content, heading containing emoji or non-ASCII.
  - Idempotency test on at least 3 representative inputs.
  - Integration test: full `postprocess` chain on a representative inline string with all three noise types present, asserts cleaning behavior.
  - Existing tests in `test_convert.py` must continue to pass on the existing `sample.pdf` fixture — the new pass must not break extraction of normal documents.
- **Type-hinted.** Match existing style — `from __future__ import annotations`, function-level annotations, `tuple[str, int]` not `Tuple[str, int]`.
- **Graceful with malformed input.** Empty string → empty string. No h2s → input unchanged. Single h2 → input unchanged (no prose-h2 to find = no TOC removal).

---

## Validation targets (Definition of Done)

The targets below are the bar. Concrete observed numbers in the report — not aspirations.

### 1. h2 count reduction

Process each of the 12 files in `outputs/` and compare to original. Target totals:
- **Total across 12 files: ≤ 400 h2 (down from 976 raw)**

Stretch targets for the worst offenders (don't tune to overfit, but these are the headline numbers):
- `Behavioral_Handbook.md`: 119 → target ≤ 60
- `TMAY Compendium.md`: 164 → target ≤ 80
- `Why This Role Bible.md`: 255 → target ≤ 120

If a target is missed, report observed numbers and explain. Don't tune heuristics to overfit per-file. Reasoning beats target-chasing.

### 2. HTML entities: 0 across all 12 files

After postprocess, `grep -c '&amp;\|&gt;\|&lt;\|&quot;\|&#39;\|&nbsp;'` across all outputs must return 0.

### 3. No body text lost outside TOC regions

For each of Behavioral Handbook, TMAY Compendium, Email Templates: compute word count of body text excluding TOC regions, before and after. Approximately equal (within ~5% — image-ref deletion and minor formatting differences can affect counts). Surface the numbers in the report.

### 4. Idempotency

`postprocess(postprocess(x)) == postprocess(x)` for at least 3 representative inputs (one of each TOC pattern + one no-TOC). Bake this into a unit test.

### 5. Existing tests still pass

`make test` passes. The existing `tests/test_convert.py` covering `sample.pdf` continues to pass without modification.

### 6. Documentation

- README updated with a new section explaining the post-processing pass: what it cleans, why, the standalone re-processing entry point.
- Module docstring in `postprocess.py` summarizes the three cleanups.
- Each heuristic function has a docstring with WHY + concrete example.

---

## Iteration loop (suggested)

Don't re-run docling extraction during iteration. The existing `outputs/` directory has all 12 outputs from Apr 27 — sufficient for tuning.

1. Implement one heuristic.
2. Run against `outputs/Behavioral_Handbook/Behavioral_Handbook.md` (worst-case: table-form TOC + many fragment headings + many entities).
3. Check stats output. Diff against original for unexpected changes.
4. Run against `outputs/TMAY Compendium/TMAY Compendium.md` and `outputs/Email Templates/Email Templates.md` (orphan-h2-run TOC).
5. Run against minimal-noise files (`outputs/TMAY Rubric/`, `outputs/Presentation Checklist/`) — make sure heuristics don't over-clean these.
6. Once all heuristics in place, run full batch and capture per-file before/after stats.

**Don't write to `outputs/` while iterating** — that directory is operator-owned. Write tmp files for inspection. Once tests are green, run the integration via `convert_one` against the existing test fixture (which writes to `tmp_path`).

---

## Out of scope

- The brain repo (`/home/jhorsey/repos/fr-consulting/brain`). The downstream stage — copy cleaned outputs into `brain/knowledge/`, remove band-aids in `scripts/build-manifest.mjs`, rebuild manifest, regression test — happens AFTER this work merges. Do not touch the brain.
- docling version bumps or `pipeline_options` changes. The noise we're fixing is post-extraction; bumping docling won't dedupe TOCs.
- Refactors of `_prune_repeated_images`, `_make_converter`, batch driver, CLI structure beyond the new entry point. These work — leave alone.
- Performance work on docling extraction.
- New CLI features unrelated to the postprocess flow.
- Hard-coding consulting-specific cleanup rules (e.g., "always strip 'The Investment Banking Blueprint' from h2"). The tool is general-purpose; rules must be structural, not content-based.

---

## Reporting

**Branch:** `worker/markdown-postprocess`
**Worktree:** `/home/jhorsey/repos/automations/wt-pdf-to-markdown-converter-markdown-postprocess`
**Report to:** `.claude/reports/markdown-postprocess.md`

**Reporting format** (when done):

```
# pdf2md markdown post-processing pass

STATUS: DONE

Branch: worker/markdown-postprocess
Commits:
- <sha> — <subject>
- <sha> — <subject>
- ...

DoD verified:
- [x] All 12 files processed; per-file h2 counts before/after table.
- [x] Total h2 across 12 files: <N> (target ≤ 400, from 976 raw).
- [x] HTML entities across all 12 files: 0.
- [x] Body word-count delta on 3 sample files within 5%.
- [x] Idempotency test passes.
- [x] `make test` passes (all existing + new tests).
- [x] README updated; module/function docstrings present.

Per-file h2 count table:
| File                                  | Raw  | After |
|---------------------------------------|------|-------|
| Behavioral Handbook                   | 119  | ...   |
| ...                                   | ...  | ...   |

Non-obvious decisions (5-8 bullets):
- How "prose-like" body was finalized (any tweaks to the proposed signals)
- How label-form heading detection avoids demoting real colon-bearing headings
- Which standalone entry point (CLI flag vs script) was picked and why
- Any heuristic that surprised you on real data
- Anything you flagged as borderline (real h2 demoted, or noise retained)
- Notes on observed corner cases that the tests now cover
```

**On ambiguity:** Stop and write `STATUS: QUESTION` to the report path. Specifically pause for:
- h2-count targets unreachable without overfitting → report observed numbers, ask whether to retune.
- A heuristic fails on one of the 12 files in a way that doesn't fit any documented pattern → surface the failure rather than special-casing.
- Anything that suggests the brain side needs to be touched (the answer is no — but report what you observed).

For low-stakes binary choices (CLI flag vs script, dataclass shape, etc.): pick one, justify in the report, don't block.

---

## Working state at handoff

- pdf2md HEAD: this commit (handoff brief + .claude/ scaffold)
- pdf2md `outputs/` directory: populated with Apr 27 extractions (the source-of-truth for iteration; do not overwrite)
- pdf2md `tests/fixtures/`: existing `sample.pdf` + `sample_with_image.pdf` for integration testing
- Working tree: clean

Operator-style notes that may help (carried from brain primary):
- Operator wants you to drive — make judgment calls, name the load-bearing ones in your report.
- Conservative defaults are valued. When choosing between a "more aggressive" and a "safer" heuristic, take the safer one.
- Primary-source evidence matters. If a heuristic disagrees with what's actually in the files, trust the files.
- Push to main is fine for primary integration; you commit to `worker/markdown-postprocess` and stop. Primary handles merge.
