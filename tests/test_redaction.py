"""Secret redaction: credentials must never reach the LLM, the DB or traces."""

from assistant.redaction import PLACEHOLDER, redact


def test_redacts_provider_keys():
    r = redact("my key is gsk_abcdefghijklmnopqrstuvwxyz0123 please help")
    assert "gsk_" not in r.text and PLACEHOLDER in r.text and r.had_secrets


def test_redacts_credential_assignment_but_keeps_sentence():
    r = redact("The ingestion key: ak_live_12345abcde for project X")
    assert "ak_live_12345abcde" not in r.text
    assert r.text.startswith("The ingestion key:")


def test_redacts_bearer_and_long_tokens():
    r = redact("Authorization: Bearer abcDEF1234567890ghijkl and 9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e")
    assert "abcDEF1234567890ghijkl" not in r.text
    assert "9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e" not in r.text


def test_leaves_normal_questions_untouched():
    q = "What is the ingestion rate limit on Team for INC-2025-12 and version 2.3.1?"
    r = redact(q)
    assert r.text == q and not r.had_secrets
