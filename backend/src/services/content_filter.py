from __future__ import annotations

import re
from typing import List, Tuple


_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.I),
    re.compile(r"disregard\s+(your|all|the)\s+(instructions?|rules?|guidelines?)", re.I),
    re.compile(r"(system|assistant)\s*:\s*", re.I),
    re.compile(r"<\s*(system|instructions?|prompt)\s*>", re.I),
    re.compile(r"\bjailbreak\b", re.I),
    re.compile(r"you\s+are\s+now\s+(?!creating|an?\s+expert)", re.I),
    re.compile(r"act\s+as\s+(if\s+you\s+are|a)\s+(?!training|an?\s+expert)", re.I),
    re.compile(r"forget\s+(everything|all)\s+(you|I)\s+(know|told)", re.I),
]

_MAX_CHARS = 80_000


def check_prompt_injection(text: str) -> Tuple[bool, str]:
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return False, f"偵測到可疑指令片段：'{match.group()}'"
    return True, ""


def sanitize_for_prompt(text: str) -> str:
    text = text.replace("\x00", "")
    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS] + "\n[內容因超過長度上限已截斷]"
    return text
