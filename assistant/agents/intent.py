"""Rule-based memory-intent detection, used ONLY when the LLM is unavailable.

Normally the Coordinator and Memory Agent (LLMs) understand memory requests. If the
provider is down or rate-limited, users must still be able to see and erase what is
remembered about them, so these few unambiguous patterns are handled in code.
Anything more nuanced ("correct my plan to Team") is not guessed: the user is told
nothing changed and pointed to the Memory tab.
"""

from __future__ import annotations

import re
from typing import Literal

MemoryIntent = Literal["list", "forget_all", "command"]

_LIST = re.compile(
    r"\b(what (do|did) you (remember|know|recall) about me|show (me )?(my|what you) (memor|remember)|"
    r"what('s| is) (in )?my memory|list my memor)", re.I)
_FORGET_ALL = re.compile(r"\bforget (everything|all)\b|\b(delete|erase|wipe) (all )?(my )?memor(y|ies)\b", re.I)
_COMMAND = re.compile(
    r"^\s*(please\s+)?(remember|forget|correction|correct my|update my memory)\b|"
    r"\b(remember (that|this|it)|forget (that|my|what|about))\b", re.I)


def memory_intent(text: str) -> MemoryIntent | None:
    """Classify clear memory requests; None for everything else (questions go to research)."""
    if _LIST.search(text):
        return "list"
    if _FORGET_ALL.search(text):
        return "forget_all"
    if _COMMAND.search(text) and "?" not in text:
        return "command"
    return None
