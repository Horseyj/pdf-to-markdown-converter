"""Tests for pdf2md.postprocess."""

from __future__ import annotations

from pdf2md.postprocess import (
    LAYOUT_ARTIFACT_BODY_THRESHOLD,
    MAX_HEADING_CHARS,
    MAX_NUMBERED_STEP_TEXT_CHARS,
    PostprocessStats,
    decode_html_entities,
    demote_fragment_headings,
    postprocess,
    remove_toc_region,
)


# --- decode_html_entities ----------------------------------------------------


def test_decode_named_entities():
    text = "Firm- &amp; Role-specific. M&amp;A transactions. why &gt; other?"
    out, n = decode_html_entities(text)
    assert "&amp;" not in out
    assert "Firm- & Role-specific" in out
    assert "M&A transactions" in out
    assert "why > other?" in out
    assert n == 3


def test_decode_numeric_and_apos_entities():
    text = "It&#39;s &nbsp; here. &lt;tag&gt; and &quot;quote&quot;"
    out, n = decode_html_entities(text)
    assert "It's" in out
    assert "<tag>" in out
    assert '"quote"' in out
    assert n == 6


def test_decode_idempotent():
    text = "A &amp; B &gt; C"
    once, _ = decode_html_entities(text)
    twice, n_second = decode_html_entities(once)
    assert once == twice
    assert n_second == 0


def test_decode_empty_input():
    out, n = decode_html_entities("")
    assert out == ""
    assert n == 0


def test_decode_preserves_text_with_no_entities():
    text = "Just plain text. No entities here."
    out, n = decode_html_entities(text)
    assert out == text
    assert n == 0


# --- remove_toc_region -------------------------------------------------------


def test_toc_orphan_h2_run_pattern():
    """Pattern B: ## Contents followed by orphan h2s until first prose h2."""
    text = (
        "# Title\n\n"
        "## Contents\n\n"
        "## SECTION ONE\n\n"
        "## SECTION TWO\n\n"
        "## Real Section\n\n"
        "This is a real paragraph that runs at least two hundred chars long "
        "to make sure the prose-line criterion fires here. It needs to be long "
        "enough to convince the postprocessor this is real content not a TOC.\n"
    )
    out, n = remove_toc_region(text)
    assert n == 1
    assert "## Contents" not in out
    assert "## SECTION ONE" not in out
    assert "## SECTION TWO" not in out
    assert "## Real Section" in out


def test_toc_table_form_pattern():
    """Pattern A: ## Contents with a markdown table body."""
    text = (
        "## Contents\n\n"
        "| HOWTOUSE                                       |\n"
        "|------------------------------------------------|\n"
        "| BEHAVIORALCHEATSHEET                          |\n"
        "\n"
        "## INVESTMENT BANKING LANDSCAPE QUESTIONS\n\n"
        "Common Questions & Answers\n\n"
        "## Real Section\n\n"
        "Real content paragraph that easily clears two hundred chars in length, "
        "padded out with more words so the prose-line heuristic registers it "
        "as the first real-content section and the TOC region terminates here.\n"
    )
    out, n = remove_toc_region(text)
    assert n == 1
    assert "## Contents" not in out
    assert "HOWTOUSE" not in out
    assert "## INVESTMENT BANKING" not in out
    assert "## Real Section" in out
    assert "Real content paragraph" in out


def test_toc_table_of_contents_alias_matches():
    text = (
        "## Table of Contents\n\n"
        "## Orphan One\n\n"
        "## Real\n\n"
        + ("A " * 120) + "\n"  # 240 chars
    )
    out, n = remove_toc_region(text)
    assert n == 1
    assert "## Table of Contents" not in out
    assert "## Real" in out


def test_toc_case_insensitive():
    text = (
        "## contents\n\n"
        "## Orphan\n\n"
        "## Real\n\n"
        + ("X " * 110) + "\n"
    )
    out, n = remove_toc_region(text)
    assert n == 1


def test_toc_no_contents_heading_is_noop():
    text = "## Foo\n\nbody\n\n## Bar\n\nbody\n"
    out, n = remove_toc_region(text)
    assert n == 0
    assert out == text


def test_toc_no_following_prose_h2_leaves_unchanged():
    """Brochure-style PDF where every h2 has only short fragments. Conservative
    default: leave it untouched rather than risk deleting content."""
    text = (
        "## Contents\n\n"
        "## Short Heading One\n\n"
        "tiny\n\n"
        "## Short Heading Two\n\n"
        "tiny\n"
    )
    out, n = remove_toc_region(text)
    assert n == 0
    assert out == text


def test_toc_contents_is_only_h2_leaves_unchanged():
    text = "## Contents\n\nsome lines that are not headings\n"
    out, n = remove_toc_region(text)
    assert n == 0
    assert out == text


def test_toc_multiple_contents_only_first_handled():
    """Brief: 'multiple ## Contents headings (only first matters).' The second
    one survives this pass and is left for the empty-body demoter."""
    long_para = ("p " * 110) + "."
    text = (
        "## Contents\n\n"
        "## Orphan\n\n"
        "## First Real\n\n"
        f"{long_para}\n\n"
        "## Contents\n\n"
        "## Later\n\n"
        f"{long_para}\n"
    )
    out, n = remove_toc_region(text)
    assert n == 1
    # First Contents removed; second remains.
    assert out.count("## Contents") == 1


def test_toc_orphan_h2_run_with_short_bullet_sub_entries():
    """TOC bullets like ``- 2.A: ...`` must NOT register as prose-like —
    they're short TOC sub-entries, not real content. The walk continues
    until we find a section whose body has real prose."""
    text = (
        "## Contents\n\n"
        "## SECTION 1: OVERVIEW\n\n"
        "## SECTION 2: STRUCTURE\n\n"
        "- 2.A: Combining Reasons\n"
        "- 2.B: Experience-Based vs. Interest-Based Reasons\n\n"
        "## SECTION 3: WHAT GOOD LOOKS LIKE\n\n"
        "## Purpose of the Question\n\n"
        + ("Real prose answering the question with enough length to clearly cross "
           "the two-hundred-character minimum the postprocessor checks for. "
           "Padding text to make the criterion fire reliably.")
        + "\n"
    )
    out, n = remove_toc_region(text)
    assert n == 1
    assert "## SECTION 1: OVERVIEW" not in out
    assert "## SECTION 2: STRUCTURE" not in out
    assert "- 2.A:" not in out
    assert "## SECTION 3: WHAT GOOD LOOKS LIKE" not in out
    assert "## Purpose of the Question" in out


def test_toc_walks_past_real_short_h2_with_substantive_bullets():
    """A real prose section with bullets and a longish paragraph stops the walk
    even when no single line is 200+ chars (TMAY Compendium case)."""
    text = (
        "## Contents\n\n"
        "## WALK ME THROUGH YOUR RESUME\n\n"
        "## GENERAL TMAYS\n\n"
        "TMAY Example #1\n\n"
        "TMAY Example #2\n\n"
        "## Walk Me Through Your Resume\n\n"
        "- If your TMAY includes all your Resume experience…\n"
        "- no adjustments needed.\n"
        "- If your TMAY doesn't include all your Resume experiences…\n"
        "- Preface your TMAY with the following…\n\n"
        "'Sure but if you don't mind could I share some things outside of "
        "my Resume just to give you context to what's on it?'\n\n"
        "- And then wait for nod of approval before launching into your TMAY.\n"
    )
    out, n = remove_toc_region(text)
    assert n == 1
    assert "## WALK ME THROUGH YOUR RESUME" not in out
    assert "## GENERAL TMAYS" not in out
    assert "TMAY Example #1" not in out
    assert "## Walk Me Through Your Resume" in out
    assert "If your TMAY includes" in out


def test_toc_empty_input_is_noop():
    out, n = remove_toc_region("")
    assert out == ""
    assert n == 0


def test_toc_idempotent():
    text = (
        "## Contents\n\n"
        "## Orphan\n\n"
        "## Real\n\n"
        + ("X " * 110) + "\n"
    )
    once, _ = remove_toc_region(text)
    twice, n_second = remove_toc_region(once)
    assert once == twice
    assert n_second == 0


# --- demote_fragment_headings ------------------------------------------------


def test_demote_ellipsis_curly():
    text = (
        "## Behavioral Questions evaluate a candidate's…\n\n"
        "- Item one\n"
        "- Item two\n"
    )
    out, counts = demote_fragment_headings(text)
    assert counts["ellipsis"] == 1
    assert out.startswith("Behavioral Questions evaluate a candidate's…\n")
    assert "## Behavioral Questions" not in out


def test_demote_ellipsis_three_dots():
    text = (
        "## The ideal candidate is...\n\n"
        "- smart\n"
        "- hardworking\n"
    )
    out, counts = demote_fragment_headings(text)
    assert counts["ellipsis"] == 1
    assert "## The ideal candidate" not in out


def test_demote_overlong_heading():
    long_text = "This is a very long heading text " * 5  # ~165 chars
    text = f"## {long_text}\n\nbody\n"
    out, counts = demote_fragment_headings(text)
    assert counts["overlong"] == 1
    assert "## " not in out.splitlines()[0]


def test_demote_overlong_threshold_boundary():
    short = "X" * (MAX_HEADING_CHARS - 1)
    text = f"## {short}\n\nbody\n"
    _, counts = demote_fragment_headings(text)
    assert counts["overlong"] == 0


def test_demote_label_form_followed_by_dash_bullets():
    text = (
        "## Strong reasons to include:\n\n"
        "- One\n"
        "- Two\n"
    )
    out, counts = demote_fragment_headings(text)
    assert counts["label"] == 1
    assert "## Strong reasons" not in out


def test_demote_label_form_followed_by_numbered_list():
    text = (
        "## Step-by-Step Structure:\n\n"
        "1. First\n"
        "2. Second\n"
    )
    out, counts = demote_fragment_headings(text)
    assert counts["label"] == 1


def test_demote_label_form_with_space_before_colon():
    """Some docling outputs have a stray space before the colon."""
    text = (
        "## Always frame it as an improvement story :\n\n"
        "- frame thing\n"
    )
    _, counts = demote_fragment_headings(text)
    assert counts["label"] == 1


def test_label_form_followed_by_prose_is_not_demoted():
    """Colon + prose is a real heading, not a fragment."""
    text = (
        "## Step-by-Step Structure:\n\n"
        "This is a normal paragraph, not a list.\n"
    )
    _, counts = demote_fragment_headings(text)
    assert counts["label"] == 0


def test_demote_layout_artifact_empty_body():
    """An h2 followed immediately by another h2 has empty body — demote."""
    text = (
        "## Why this City?\n\n"
        "## Framework\n\n"
        "Real prose content that exists in the Framework section.\n"
    )
    out, counts = demote_fragment_headings(text)
    assert counts["layout"] == 1
    assert "## Why this City?" not in out
    assert "Why this City?" in out
    assert "## Framework" in out


def test_demote_layout_artifact_image_only_body():
    """A body containing only image refs counts as empty."""
    text = (
        "## Common Questions & Answers\n\n"
        "![Image](path/img.png)\n\n"
        "## Next Section\n\n"
        + ("This following section has substantive body content that goes well "
           "past the layout-artifact threshold so only the first h2 gets demoted.")
        + "\n"
    )
    out, counts = demote_fragment_headings(text)
    assert counts["layout"] == 1
    assert "## Common Questions & Answers" not in out
    assert "## Next Section" in out


def test_demote_layout_artifact_cover_chrome():
    """Doc title and document chrome at the start get demoted by 3d."""
    text = (
        "## The Investment Banking Blueprint\n\n"
        "## TMAY Rubric\n\n"
        "## Memorability\n\n"
        + ("Memorability measures how well your TMAY sticks in the interviewer's "
           "mind and distinguishes you from other candidates over a long horizon.")
        + "\n"
    )
    out, counts = demote_fragment_headings(text)
    # Both cover-chrome h2s have empty bodies and get demoted as 3d.
    assert counts["layout"] == 2
    assert "## The Investment Banking Blueprint" not in out
    assert "## TMAY Rubric" not in out
    assert "## Memorability" in out


def test_layout_artifact_does_not_fire_on_substantive_body():
    """Body with > 50 chars of text is real content; don't demote."""
    text = (
        "## Real Section\n\n"
        "This body has more than fifty chars of real text content here.\n"
    )
    _, counts = demote_fragment_headings(text)
    assert counts["layout"] == 0


def test_demote_idempotent():
    text = (
        "## Cover Chrome\n\n"
        "## Real\n\n"
        "Substantial body content that runs to well past the layout threshold "
        "with plenty to spare so it isn't itself caught by the demote pass.\n"
    )
    once, _ = demote_fragment_headings(text)
    twice, counts_second = demote_fragment_headings(once)
    assert once == twice
    assert sum(counts_second.values()) == 0


def test_demote_does_not_touch_h3():
    text = "### Foo\n\n### Bar\n"
    out, counts = demote_fragment_headings(text)
    assert sum(counts.values()) == 0
    assert out == text


def test_demote_subtypes_attributed_in_order():
    """A heading matching multiple rules is counted under the first match."""
    # Ellipsis trumps both layout-empty-body and overlong, per the demote logic.
    long_ellipsis = "A" * (MAX_HEADING_CHARS + 5) + "…"
    text = (
        f"## {long_ellipsis}\n\n"
        "## Next Section\n\n"
        + ("Substantive body content that crosses the layout threshold so "
           "only the ellipsis heading is counted for demotion accounting.")
        + "\n"
    )
    _, counts = demote_fragment_headings(text)
    assert counts["ellipsis"] == 1
    assert counts["overlong"] == 0
    assert counts["layout"] == 0


def test_demote_empty_input():
    out, counts = demote_fragment_headings("")
    assert out == ""
    assert sum(counts.values()) == 0


def test_demote_no_h2s():
    text = "Just paragraph text\nand more text\n"
    out, counts = demote_fragment_headings(text)
    assert out == text
    assert sum(counts.values()) == 0


def test_demote_unicode_and_emoji_in_heading():
    """Non-ASCII content in heading text must round-trip through demotion."""
    text = (
        "## 📋 Schritte überprüfen…\n\n"
        "- a\n"
        "- b\n"
    )
    out, counts = demote_fragment_headings(text)
    assert counts["ellipsis"] == 1
    assert "📋 Schritte überprüfen…" in out


# --- numbered-step subtype ---------------------------------------------------


def test_demote_numbered_step_short_text():
    """A `## 1. Innovation`-style step label gets demoted, even with substantive body."""
    text = (
        "## 1. Innovation\n\n"
        + ("Innovation matters because of XYZ. " * 30) + "\n"
    )
    out, counts = demote_fragment_headings(text)
    assert counts["numbered_step"] == 1
    assert "## 1. Innovation" not in out
    assert "1. Innovation" in out


def test_demote_numbered_step_full_sentence():
    """A numbered-step with a full sentence under threshold gets demoted."""
    text = (
        "## 1. Reaffirm your commitment to finance.\n\n"
        + ("Step content paragraph here. " * 30) + "\n"
    )
    _, counts = demote_fragment_headings(text)
    assert counts["numbered_step"] == 1


def test_demote_numbered_step_bare_number():
    """A bare `## 3.` is unambiguous noise — demote regardless of body length."""
    text = (
        "## 3.\n\n"
        + ("Body text that is well over fifty chars so layout-artifact "
           "doesn't fire — we want to ensure numbered_step specifically "
           "claims this demotion.")
        + "\n"
    )
    out, counts = demote_fragment_headings(text)
    assert counts["numbered_step"] == 1
    assert counts["layout"] == 0
    assert "## 3." not in out
    assert "3." in out  # text survives


def test_demote_numbered_step_at_threshold_boundary():
    """A heading exactly at MAX_NUMBERED_STEP_TEXT_CHARS still demotes; one over does not."""
    at_limit = "X" * MAX_NUMBERED_STEP_TEXT_CHARS
    over_limit = "X" * (MAX_NUMBERED_STEP_TEXT_CHARS + 1)
    body = ("Body that crosses the layout threshold so we isolate the "
            "numbered-step decision from the layout-artifact check.") + "\n"

    text_at = f"## 1. {at_limit}\n\n{body}"
    _, counts_at = demote_fragment_headings(text_at)
    assert counts_at["numbered_step"] == 1

    text_over = f"## 1. {over_limit}\n\n{body}"
    _, counts_over = demote_fragment_headings(text_over)
    assert counts_over["numbered_step"] == 0


def test_numbered_step_section_anchor_with_letter_not_demoted():
    """Real subsection patterns like `## 4.A: ...` lack whitespace after the
    period and must NOT match the numbered-step rule."""
    text = (
        "## 4.A: Firm- and Group-Specific Adjustments\n\n"
        + ("Adjustment context paragraph. " * 30) + "\n"
        "## 11.C: 4 Credible Reasons for Choosing Sales & Trading\n\n"
        + ("Reasons content paragraph. " * 30) + "\n"
    )
    out, counts = demote_fragment_headings(text)
    assert counts["numbered_step"] == 0
    assert "## 4.A: Firm- and Group-Specific Adjustments" in out
    assert "## 11.C: 4 Credible Reasons for Choosing Sales & Trading" in out


def test_numbered_step_ranks_before_layout():
    """A numbered-step with empty body should attribute to numbered_step,
    not layout — order in the chain matters for stats."""
    text = (
        "## 1. Short Step\n\n"  # empty body would otherwise be 3e layout
        "## Next\n\n"
        + ("Body text long enough to keep Next out of any demote bucket. " * 5)
        + "\n"
    )
    _, counts = demote_fragment_headings(text)
    assert counts["numbered_step"] == 1
    assert counts["layout"] == 0


def test_numbered_step_in_postprocess_stats():
    """End-to-end: numbered-step demotions surface in stats."""
    text = (
        "## 1. Reaffirm your commitment to finance.\n\n"
        + ("Step body. " * 30) + "\n\n"
        "## 2. Show your engagement.\n\n"
        + ("Step body. " * 30) + "\n\n"
        "## Real Section\n\n"
        + ("Real content paragraph. " * 30) + "\n"
    )
    _, stats = postprocess(text)
    assert stats.headings_demoted_numbered_step == 2
    assert stats.total_headings_demoted == 2


def test_numbered_step_idempotent():
    """After demotion, the plain-text line `1. Foo` must not re-match the h2 regex."""
    text = (
        "## 1. First step text here.\n\n"
        + ("Body content. " * 25) + "\n"
    )
    once, _ = postprocess(text)
    twice, counts_second = postprocess(once)
    assert once == twice
    assert counts_second.headings_demoted_numbered_step == 0


# --- postprocess (integration) -----------------------------------------------


def test_postprocess_chain_runs_all_three_passes():
    """A representative document with all three noise types."""
    text = (
        "<!-- source: x.pdf -->\n\n"
        "![Image](x_artifacts/000.png)\n\n"
        "## The Investment Banking Blueprint\n\n"
        "## Behavioral Handbook\n\n"
        "## Contents\n\n"
        "## INVESTMENT BANKING LANDSCAPE QUESTIONS\n\n"
        "Common Questions &amp; Answers\n\n"
        "![Image](x_artifacts/001.png)\n\n"
        "## How to Use This Handbook\n\n"
        + ("This handbook covers the four main types of behavioral questions "
           "you'll face in any interview, and gives you both the frameworks "
           "to structure your answers and real examples to follow.")
        + "\n\n"
        "## Behavioral Questions evaluate a candidate's…\n\n"
        "- Motivations\n"
        "- Communication\n\n"
        "## Strong reasons to include:\n\n"
        "- one\n"
        "- two\n\n"
        "## Closing &amp; Summary\n\n"
        "Real long closing summary text that is well above two hundred chars "
        "in length so the body counts as substantive prose under the heuristic "
        "and does not get pulled into the TOC region or demoted by any rule.\n"
    )
    out, stats = postprocess(text)

    # Entity decode — no &amp; anywhere.
    assert "&amp;" not in out

    # TOC removal: ## Contents and ## INVESTMENT BANKING ... gone.
    assert "## Contents" not in out
    assert "## INVESTMENT BANKING LANDSCAPE QUESTIONS" not in out

    # First real section preserved.
    assert "## How to Use This Handbook" in out

    # Cover chrome demoted (layout subtype).
    assert "## The Investment Banking Blueprint" not in out
    assert "## Behavioral Handbook" not in out
    assert "The Investment Banking Blueprint" in out
    assert "Behavioral Handbook" in out

    # Ellipsis fragment demoted.
    assert "## Behavioral Questions evaluate a candidate's…" not in out
    assert "Behavioral Questions evaluate a candidate's…" in out

    # Label-form demoted.
    assert "## Strong reasons to include:" not in out

    # Final h2 (substantive body) preserved.
    assert "## Closing & Summary" in out

    # Stats look right.
    assert stats.entities_decoded >= 2
    assert stats.toc_regions_removed == 1
    assert stats.headings_demoted_layout >= 2  # Blueprint + Handbook
    assert stats.headings_demoted_ellipsis == 1
    assert stats.headings_demoted_label == 1


def test_postprocess_idempotent_pattern_a():
    """Idempotency on a table-form TOC document."""
    text = (
        "## Contents\n\n"
        "| FOO |\n|-----|\n| BAR |\n\n"
        "## Real\n\n"
        + ("R " * 110) + "\n"
    )
    once, _ = postprocess(text)
    twice, _ = postprocess(once)
    assert once == twice


def test_postprocess_idempotent_pattern_b():
    """Idempotency on an orphan-h2-run TOC document."""
    text = (
        "## Contents\n\n"
        "## Orphan One\n\n"
        "## Orphan Two\n\n"
        "## Real\n\n"
        + ("R " * 110) + "\n"
    )
    once, _ = postprocess(text)
    twice, _ = postprocess(once)
    assert once == twice


def test_postprocess_idempotent_no_toc():
    """Idempotency on a clean document with no Contents heading."""
    text = (
        "## Section A\n\n"
        + ("Real content paragraph " * 12) + "\n\n"
        "## Section B\n\n"
        + ("More real content " * 12) + "\n"
    )
    once, _ = postprocess(text)
    twice, _ = postprocess(once)
    assert once == twice


def test_postprocess_empty_input():
    out, stats = postprocess("")
    assert out == ""
    assert stats.total_headings_demoted == 0
    assert stats.toc_regions_removed == 0
    assert stats.entities_decoded == 0


def test_postprocess_single_line_input():
    out, _ = postprocess("just one line\n")
    assert out == "just one line\n"


def test_postprocess_only_h2s_no_body():
    """Stress: doc that's all h2s with empty bodies."""
    text = "## A\n\n## B\n\n## C\n"
    out, stats = postprocess(text)
    # All three h2s have empty bodies → all demoted as layout artifacts.
    assert stats.headings_demoted_layout == 3
    assert "## " not in out


def test_postprocess_preserves_provenance_header():
    """The provenance comment lines must not be touched."""
    text = (
        "<!-- source: foo.pdf -->\n"
        "<!-- pages: 10 -->\n"
        "<!-- extractor: docling 2.91.0 -->\n\n"
        "## Real\n\n"
        + ("X " * 110) + "\n"
    )
    out, _ = postprocess(text)
    assert out.startswith("<!-- source: foo.pdf -->\n")
    assert "<!-- pages: 10 -->" in out
    assert "<!-- extractor: docling 2.91.0 -->" in out


def test_stats_summary_string():
    stats = PostprocessStats(
        entities_decoded=41,
        toc_regions_removed=1,
        headings_demoted_layout=20,
        headings_demoted_ellipsis=3,
    )
    s = stats.summary()
    assert "TOC removed" in s
    assert "23 headings demoted" in s
    assert "41 entities decoded" in s


def test_stats_summary_no_changes():
    assert PostprocessStats().summary() == "no changes"
