"""Secret detection and redaction.

User text is redacted *before* it reaches the agents, the LLM provider, the
database, or LangSmith traces. This is the single choke point that keeps
credentials out of stored memory and shared traces (an explicit assignment rule,
and also what the corpus itself asks: "never paste actual keys", ingest:0).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Each pattern targets a common credential shape. Order matters: specific
# provider formats first, generic "password=..." style assignments last.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("groq_key", re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("langsmith_key", re.compile(r"\blsv2_[A-Za-z0-9_]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.=]{16,}")),
    # Asterline ingestion keys have no documented format, so catch explicit mentions.
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(password|passwd|pwd|secret|api[_\s-]?key|ingestion[_\s-]?key|token|access[_\s-]?key)"
            r"(\s*(?:is|=|:)\s*)([^\s,;]{6,})"
        ),
    ),
    # Long random-looking strings (32+ chars mixing letters and digits) are treated as secrets.
    ("high_entropy", re.compile(r"\b(?=[A-Za-z0-9_\-]*\d)(?=[A-Za-z0-9_\-]*[A-Za-z])[A-Za-z0-9_\-]{32,}\b")),
]

PLACEHOLDER = "[REDACTED_SECRET]"


@dataclass
class RedactionResult:
    """Redacted text plus the kinds of secrets that were removed (never the values)."""

    text: str
    found: list[str]

    @property
    def had_secrets(self) -> bool:
        return bool(self.found)


def redact(text: str) -> RedactionResult:
    """Replace every secret-looking substring with a placeholder."""
    found: list[str] = []
    for kind, pattern in _SECRET_PATTERNS:
        if kind == "credential_assignment":
            # Keep the label ("password is") so the sentence still reads naturally.
            def _keep_label(m: re.Match[str]) -> str:
                return f"{m.group(1)}{m.group(2)}{PLACEHOLDER}"

            text, n = pattern.subn(_keep_label, text)
        else:
            text, n = pattern.subn(PLACEHOLDER, text)
        if n:
            found.append(kind)
    return RedactionResult(text=text, found=found)


def contains_secret(text: str) -> bool:
    """True when `text` still contains a secret or a redaction placeholder."""
    return PLACEHOLDER in text or redact(text).had_secrets
