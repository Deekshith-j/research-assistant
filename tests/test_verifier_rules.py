"""Deterministic citation checks used by the Verifier Agent."""

from assistant.agents.verifier import deterministic_issues, extract_citations


def test_extracts_single_and_grouped_citations():
    text = "Team costs $449 [pricing:0]. Retention differs [pricing:1, traces:1] and see [release-23:0]."
    assert extract_citations(text) == ["pricing:0", "pricing:1", "traces:1", "release-23:0"]


def test_accepts_full_width_brackets():
    # Regression test: gpt-oss models cite as 【pricing:0】 (found by the baseline evaluation).
    assert extract_citations("Team costs $449【pricing:0】【pricing:1】") == ["pricing:0", "pricing:1"]


def test_ignores_non_citation_brackets():
    assert extract_citations("Use [REDACTED_SECRET] or [link](x)") == []


def test_flags_ids_not_in_evidence():
    draft = {"status": "answered", "answer": "Fact [pricing:9]", "claims": []}
    issues = deterministic_issues(draft, {"pricing:0"})
    assert any("pricing:9" in i for i in issues)


def test_flags_answer_without_citations():
    draft = {"status": "answered", "answer": "Team costs $449.", "claims": []}
    assert deterministic_issues(draft, {"pricing:0"})


def test_claims_without_inline_citations_are_flagged():
    # Regression test for R16: ids only in the claims list never reach the user's Sources.
    draft = {"status": "answered", "answer": "Stipend is $175 - handbook:1",
             "claims": [{"statement": "Stipend is $175", "chunk_ids": ["handbook:1"]}]}
    assert deterministic_issues(draft, {"handbook:1"})


def test_abstention_without_citations_is_fine():
    draft = {"status": "insufficient_evidence", "answer": "Not documented.", "claims": []}
    assert deterministic_issues(draft, {"pricing:0"}) == []
