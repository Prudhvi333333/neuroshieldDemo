"""Input sanitization utilities for NeuroShield Gateway.

Provides lightweight, dependency-free heuristics to catch common obfuscation
attempts before they reach the LLM firewall graph.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Tuple

# Zero-width & formatting characters frequently used for prompt injection
ZERO_WIDTH_CHARS = {
    "\u200B",  # ZERO WIDTH SPACE
    "\u200C",  # ZERO WIDTH NON-JOINER
    "\u200D",  # ZERO WIDTH JOINER
    "\u2060",  # WORD JOINER
    "\uFEFF",  # ZERO WIDTH NO-BREAK SPACE
    "\u202E",  # RIGHT-TO-LEFT OVERRIDE (RTLO)
    "\u202D",  # LEFT-TO-RIGHT OVERRIDE
    "\u2066",  # LEFT-TO-RIGHT ISOLATE
    "\u2067",  # RIGHT-TO-LEFT ISOLATE
    "\u2068",  # FIRST STRONG ISOLATE
    "\u2069",  # POP DIRECTIONAL ISOLATE
}

# Base64 regex – looks for long bursts of base64 characters (including padding)
_BASE64_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")

# Cyrillic & Greek blocks commonly abused as Latin homoglyphs
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_GREEK_RE = re.compile(r"[\u0370-\u03FF]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def detect_zero_width(text: str) -> List[int]:
    """Return indices of zero-width chars found in *text*."""
    return [i for i, ch in enumerate(text) if ch in ZERO_WIDTH_CHARS]


def detect_base64_bursts(text: str) -> List[Tuple[int, int]]:
    """Return list of (start, end) indices of suspicious base64 bursts."""
    return [m.span() for m in _BASE64_RE.finditer(text)]


def _script_of(ch: str) -> str:
    """Rudimentary script classification (latin / cyrillic / greek / other)."""
    cp = ord(ch)
    if 0x0370 <= cp <= 0x03FF:
        return "greek"
    if 0x0400 <= cp <= 0x04FF:
        return "cyrillic"
    if ("LATIN" in unicodedata.name(ch, "")):
        return "latin"
    return "other"


def detect_homoglyphs(text: str) -> List[int]:
    """Detect positions of characters that mix scripts within the same word.

    Very simple heuristic: if a word contains both latin and cyrillic/greek we
    flag the non-latin characters.
    """
    findings: List[int] = []
    for match in re.finditer(r"\w+", text, flags=re.UNICODE):
        word = match.group(0)
        scripts = { _script_of(ch) for ch in word }
        if len(scripts & {"cyrillic", "greek"}) and "latin" in scripts:
            # add indices of non-latin chars inside word
            for idx, ch in enumerate(word, start=match.start()):
                if _script_of(ch) in {"cyrillic", "greek"}:
                    findings.append(idx)
    return findings


# ---------------- Sanitization pipeline ----------------

def sanitize_text(text: str) -> Tuple[str, Dict[str, List]]:
    """Return (sanitized_text, redactions) where *redactions* maps rule→positions."""
    redactions: Dict[str, List] = {}

    # Zero-width removal
    zw_pos = detect_zero_width(text)
    if zw_pos:
        redactions["zero_width"] = zw_pos
        text = "".join(ch for ch in text if ch not in ZERO_WIDTH_CHARS)

    # Homoglyphs – we replace flagged characters with "?"
    homo_pos = detect_homoglyphs(text)
    if homo_pos:
        redactions["homoglyphs"] = homo_pos
        text_list = list(text)
        for i in homo_pos:
            text_list[i] = "?"  # placeholder replacement
        text = "".join(text_list)

    # Base64 bursts – redact by truncating long sequences
    b64_spans = detect_base64_bursts(text)
    if b64_spans:
        redactions["base64_bursts"] = [list(span) for span in b64_spans]
        new_text = []
        last_end = 0
        for start, end in b64_spans:
            new_text.append(text[last_end:start])
            new_text.append("<base64_redacted>")
            last_end = end
        new_text.append(text[last_end:])
        text = "".join(new_text)

    return text, redactions


def sanitize_report(original_text: str) -> Dict[str, any]:
    """Return a structured report with decision and redactions."""
    sanitized, redactions = sanitize_text(original_text)
    blocked = bool(redactions)  # policy: block on any finding
    reasons = list(redactions.keys())
    return {
        "blocked": blocked,
        "reasons": reasons,
        "redactions": redactions,
        "sanitized_text": sanitized,
    }
