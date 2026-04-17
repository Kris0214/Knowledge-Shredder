"""
Prompt Injection 偵測與文字清理。

上傳的文件若含有惡意指令，可能操控 LLM 產生有害或偏離目標的輸出。
此模組在文字進入 LLM 前做基本防護，並不保證 100% 過濾。
"""
from __future__ import annotations

import re
from typing import List, Tuple

# ── 常見 Prompt Injection 特徵 ───────────────────────────────────────────────
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

# 單一文件的最大字元數（約 20k tokens）
_MAX_CHARS = 80_000


def check_prompt_injection(text: str) -> Tuple[bool, str]:
    """
    回傳 (is_safe, reason)。
    is_safe=False 表示偵測到疑似注入指令。
    """
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return False, f"偵測到可疑指令片段：'{match.group()}'"
    return True, ""


def sanitize_for_prompt(text: str) -> str:
    """
    移除 null bytes，並在超過長度限制時截斷文字。
    不修改任何正常金融文件內容。
    """
    text = text.replace("\x00", "")
    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS] + "\n[內容因超過長度上限已截斷]"
    return text
