"""Detect covert channel patterns in text outputs."""
from __future__ import annotations
import re
from typing import List

_ZERO_WIDTH_CHARS = {
    "\u200B", "\u200C", "\u200D", "\u2060", "\uFEFF",
}

_BASE64_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
_HEX_RE = re.compile(r"(?:0x)?[0-9A-Fa-f]{40,}")


def detect_covert_channels(text: str) -> List[str]:
    """Return list of reasons if suspicious covert channel patterns are found."""
    reasons: List[str] = []
    if any(ch in text for ch in _ZERO_WIDTH_CHARS):
        reasons.append("zero_width")
    if _BASE64_RE.search(text):
        reasons.append("base64_burst")
    if _HEX_RE.search(text):
        reasons.append("hex_burst")
    return reasons
