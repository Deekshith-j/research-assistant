"""What the assistant is allowed to remember.

The Memory Agent (an LLM) *proposes* memories; this module is the deterministic
gate that every proposal must pass before it is written. Keeping the rules in
code (not only in a prompt) means a model mistake cannot store a secret.

Remember (useful across sessions, about the *user*):
  * profile      - role/team/office, e.g. "Works in support for EU customers"
  * preference   - how they want answers, e.g. "Prefers short bullet answers"
  * work_context - ongoing work, e.g. "Investigating duplicate warehouse rows for a Team-plan customer"

Never remember:
  * credentials / tokens / keys (also redacted earlier, see redaction.py)
  * sensitive personal data (health, medical leave reasons, ...); the handbook
    itself says private medical details don't belong in shared notes (handbook:2)
  * company facts or previous answers as if they were truth: memory is never
    evidence. Facts always come from the corpus at answer time.
"""

from __future__ import annotations

import re
from typing import Literal

from assistant.redaction import contains_secret

MemoryKind = Literal["profile", "preference", "work_context"]
ALLOWED_KINDS: tuple[str, ...] = ("profile", "preference", "work_context")
MAX_MEMORY_CHARS = 280

# Words that indicate sensitive personal (special-category) information.
_SENSITIVE = re.compile(
    r"(?i)\b(diagnos\w*|medical|medication|illness|disease|pregnan\w*|therapy|therapist|"
    r"mental health|surgery|disabilit\w*|religio\w*|sexual orientation|salary|ssn|passport|"
    r"home address|bank account|credit card)\b"
)


def check_memory(kind: str, content: str) -> tuple[bool, str]:
    """Return (allowed, reason). `reason` explains rejections for the trace and the user."""
    text = content.strip()
    if kind not in ALLOWED_KINDS:
        return False, f"unknown memory kind '{kind}'"
    if not text:
        return False, "empty memory"
    if len(text) > MAX_MEMORY_CHARS:
        return False, "too long to be a focused memory"
    if contains_secret(text):
        return False, "contains a secret or credential"
    if _SENSITIVE.search(text):
        return False, "contains sensitive personal information"
    return True, "ok"
