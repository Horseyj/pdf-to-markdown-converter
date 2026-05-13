# pdf2md markdown post-processing pass

STATUS: DONE

Branch: worker/markdown-postprocess

DoD verified:
- [x] All 12 files processed; per-file h2 counts before/after table below.
- [x] Total h2 across 12 files: **683** (target ≤ 400, from 976 raw). **Target missed — reasoning below.**
- [x] HTML entities across all 12 files: **0** after postprocess (was 705).
- [x] Body word-count delta on 3 sample files (Behavioral Handbook, TMAY Compendium, Email Templates) within 5% (observed: −0.3%, −0.1%, −0.2% respectively).
- [x] Idempotency: `postprocess(postprocess(x)) == postprocess(x)` verified on all 12 real outputs AND in unit tests (3 representative inputs covering both TOC patterns + no-TOC).
- [x] `make test` equivalent: 75/75 passed (45 new postprocess tests + 30 existing). Existing `tests/test_convert.py` continues to pass on `sample.pdf`.
- [x] README updated with a new "Markdown post-processing" section explaining what it cleans, the standalone re-processing CLI flag, and the conservative-by-default rationale. Module and per-function docstrings present.

## Per-file h2 count table

| File                                  | Raw h2 | After | Δ   | Entities pre | Entities post |
|---------------------------------------|-------:|------:|----:|-------------:|--------------:|
| Behavioral_Handbook                   |    119 |    87 | −32 |           28 |             0 |
| Bullet Point Buster                   |    104 |    72 | −32 |           64 |             0 |
| Coffee Chat Handbook                  |     62 |    50 | −12 |          113 |             0 |
| Coffee Chats Advanced Tactics         |     26 |    12 | −14 |            4 |             0 |
| Email Guide                           |    102 |    72 | −30 |           84 |             0 |
| Email Templates                       |     99 |    72 | −27 |           20 |             0 |
| Presentation Checklist                |      7 |     4 |  −3 |           32 |             0 |
| Questions To Ask Your Interviewer     |     23 |    13 | −10 |           12 |             0 |
| TMAY Compendium                       |    164 |   132 | −32 |          201 |             0 |
| TMAY Rubric                           |      4 |     3 |  −1 |            4 |             0 |
| TMAY and Why this Role Examples       |     11 |     8 |  −3 |           25 |             0 |
| Why This Role Bible                   |    255 |   158 | −97 |          118 |             0 |
| **TOTAL**                             | **976** | **683** | **−293** |      **705** |         **0** |

Per-file demotion stats (subtype breakdown):

| File                                  | TOC | ellipsis | overlong | label | layout | entities |
|---------------------------------------|----:|---------:|---------:|------:|-------:|---------:|
| Behavioral_Handbook                   |   1 |        6 |        0 |     5 |     19 |       28 |
| Bullet Point Buster                   |   1 |        0 |        0 |     7 |     23 |       64 |
| Coffee Chat Handbook                  |   1 |        0 |        0 |     2 |      3 |      113 |
| Coffee Chats Advanced Tactics         |   0 |        1 |        0 |     1 |     12 |        4 |
| Email Guide                           |   1 |        0 |        0 |    10 |     16 |       84 |
| Email Templates                       |   1 |        0 |        0 |     1 |     19 |       20 |
| Presentation Checklist                |   1 |        0 |        0 |     0 |      2 |       32 |
| Questions To Ask Your Interviewer     |   1 |        1 |        0 |     0 |      4 |       12 |
| TMAY Compendium                       |   1 |        0 |        0 |     0 |     24 |      201 |
| TMAY Rubric                           |   0 |        0 |        0 |     0 |      1 |        4 |
| TMAY and Why this Role Examples       |   0 |        0 |        0 |     0 |      3 |       25 |
| Why This Role Bible                   |   1 |        0 |        0 |    48 |     36 |      118 |

## Why the h2 target was missed (and why I did not chase it)

The headline target was ≤ 400 total h2; observed 683. Stretch per-file targets were also missed: Behavioral Handbook 87 vs 60, TMAY Compendium 132 vs 80, Why This Role Bible 158 vs 120.

I inspected the residual h2s file-by-file. The overwhelming majority are legitimate section anchors with substantive bodies — e.g. in TMAY Compendium, the 132 residual h2s are dominated by `## TMAY Example #N`, `## OLD`, `## NEW`, `## Coffee Chat Version`, each appearing once per example. In Why This Role Bible, the residuals include the document's real `## 4.A:`, `## 4.B:`, `## Section 4: Why Investment Banking?`, `## Example 1 -Experiencebased…`, etc., all with prose bodies. Demoting these would lose real document structure and violate the brief's "DEMOTE, do not delete; preserve content" principle.

A small number of residuals (~15–25 across all files) are genuinely fragment-shaped — e.g. `## 3.` alone, `## Pick something personal and low-stakes.`, `## 1. Reaffirm your commitment to finance.` — but each has a non-empty prose body and none ends in `:`, `…`, or `...`. They don't match any of the five subtypes the brief documents. Catching them would require new heuristics (e.g. "h2 starting with `\d+\.` and shorter than N chars") that the brief explicitly steers away from ("Don't tune heuristics to overfit per-file. Reasoning beats target-chasing.").

I followed the brief's spec literally and report the observed numbers. If the target needs to be hit, the path forward is either a new documented subtype rule or accepting that some residual fragments are an acceptable failure mode.

## Body-text preservation (DoD #3)

Word counts on the three flagged samples, excluding the TOC region from the pre-side (same TOC remover applied to both for an apples-to-apples comparison):

| File                  | WC pre (no TOC) | WC post | Δ%    |
|-----------------------|----------------:|--------:|------:|
| Behavioral Handbook   |          10286  |   10256 | −0.3% |
| TMAY Compendium       |          35919  |   35895 | −0.1% |
| Email Templates       |           8094  |    8074 | −0.2% |

All well within the ±5% target. Drift comes from `html.unescape` collapsing multi-character entities into one character (`&amp;` 5 chars → `&` 1 char) and the demoter stripping `## ` prefixes.

## Non-obvious decisions

- **Standalone entry point: CLI flag `--postprocess-only PATH`, not a separate script.** Reuses the existing `argparse` setup, exit-code conventions, and console-script entry. A single file `pdf2md --postprocess-only outputs/x.md` or directory walk `pdf2md --postprocess-only outputs/` both work; output is rewritten in place. Less surface area to maintain than a parallel `scripts/postprocess_existing.py`.

- **"Prose-like body" criterion — the discriminator that drove the most iteration.** A single ≥200-char line, fenced code, blockquote, or >800 total chars across >3 lines are easy. The hard case was TMAY Compendium's real "## Walk Me Through Your Resume" section: short bullets (~50 chars each) and a 120-char quoted paragraph — no signal triggered. I added a fifth criterion: "any non-list, non-image, non-table paragraph line ≥ 80 chars." TOC sub-entries are either bullets-only (Why This Role Bible) or short-fragment-only (TMAY Compendium TOC) and don't trigger this; real content typically mixes a paragraph with bullets and does. The 80-char threshold is the load-bearing number.

- **Label-form (3c) requires both `:` ending AND list body.** Otherwise headings like `## Quick Clarification: 'Why [Group]?' vs. 'Why [Group] IB?'` (real heading, prose body) would be incorrectly demoted. The list-body requirement is what makes the heuristic safe.

- **Order of subtype attribution in the demoter is ellipsis → overlong → label → layout.** This is purely for stats accounting — a heading is demoted once regardless of how many rules match. The ordering matches the order documented in the brief.

- **Brief-literal TOC region behavior includes deleting empty-body h2s at the boundary.** In documents like "Why This Role Bible", the real `## Section 1: 'Why This Role?' Overview` heading appears immediately before the first prose-h2 (`## Purpose of the Question`). Per the brief's "Delete the range [Contents, first-prose-heading)" rule, that Section 1 heading is empty-body and lies within the TOC region — so it gets deleted along with the TOC. The brief author flagged this implicitly by saying the demoter would catch such cases as 3d; in practice the TOC pass takes them first. The text content under that section is empty (it's immediately followed by Purpose-of-the-Question prose), so no body text is lost — only the bare heading line.

- **HTML entity decode runs first in the chain.** This way subsequent passes see clean text: `## Common Questions & Answers` matches as a 28-char body for the layout-artifact threshold rather than 33 chars with `&amp;`. The decode is via `html.unescape` — full coverage of named/decimal/hex entities, idempotent by definition.

- **The H2 regex is `^##\s+(?!#)(.*?)\s*$`** — strict 2-hash match with at least one whitespace and a negative-lookahead for a third `#`, so `### Foo` is correctly skipped and `##Foo` (no space, not valid markdown h2) is also skipped.

## Tests

- 45 new tests in `tests/test_postprocess.py`: per-heuristic unit tests, edge cases (empty input, single line, no h2s, no Contents, brochure-style "no following prose-h2", multiple Contents, unicode/emoji), idempotency on three representative inputs (Pattern A, Pattern B, no-TOC), and an integration test exercising the full chain.
- 4 new CLI tests in `tests/test_cli.py`: single-file and directory `--postprocess-only`, missing-path exit code 2, .txt files untouched.
- 1 new convert test (`test_convert_one_runs_postprocess`): asserts the wire-in by checking the sample.pdf output has no entities after extraction.

All 75 tests pass (`pytest tests/ -v` → `75 passed in 204.27s`). The 204s wall time is dominated by docling model-load and OCR runs in the existing `test_convert.py`; the new postprocess tests alone run in ~0.1s.

## Files changed

- `src/pdf2md/postprocess.py` (new, 280 lines)
- `src/pdf2md/convert.py` (postprocess call added after `_prune_repeated_images`)
- `src/pdf2md/cli.py` (`--postprocess-only PATH` flag + `_run_postprocess_only`)
- `tests/test_postprocess.py` (new)
- `tests/test_cli.py` (3 new test cases for the flag)
- `tests/test_convert.py` (1 new test: postprocess runs in convert_one)
- `README.md` (new "Markdown post-processing" section + CLI flag in reference)
