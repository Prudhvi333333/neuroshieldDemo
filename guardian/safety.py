# guardian/safety.py
from __future__ import annotations
import re, yaml
from typing import Dict, List, Tuple
from functools import lru_cache

_ZERO_WIDTH = {"\u200B","\u200C","\u200D","\u2060","\uFEFF"}

# Default patterns – can be overridden by policy/policy.yaml
_DEFAULT_PATTERNS = {
    "self_harm": [
        r"\bkill myself\b", r"\bsuicide\b", r"\bend it all\b", r"\bself[-\s]?harm\b"
    ],
    "illicit": [
        r"\bmake (?:a|an) (?:bomb|explosive)\b",
        r"\bhow to (?:hack|break in|bypass security)\b",
        r"\bstab|poison|assassinate\b",
    ],
    "sexual": [
        r"\bexplicit sexual\b", r"\berotica\b", r"\bNSFW\b"
    ],
    "hate": [
        r"\b(?:kill|eradicate|dehumanize)\b.*\b(?:people|group|race|religion)\b",
        r"\b(?:racial slur|ethnic slur)\b",
    ],
    "pii_secret": [
        r"\bSSN\b", r"\bpassport number\b", r"\bcredit card\b",
        r"AIza[0-9A-Za-z\-_]{35}",  # Google API key
        r"(?:AKIA|ASIA)[A-Z0-9]{16}",  # AWS access key id
        r"ghp_[A-Za-z0-9]{24,40}",  # GitHub PAT
    ],
}

_SEVERITY = {
    "self_harm": "high",
    "illicit": "high",
    "hate": "high",
    "sexual": "medium",
    "pii_secret": "medium",
}

@lru_cache(maxsize=1)
def _cached_policy():
    try:
        with open("policy/policy.yaml","r",encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        p = raw.get("guardian", {}).get("safety", {})
        patterns = p.get("patterns", {}) or _DEFAULT_PATTERNS
        severity = p.get("severity", {}) or _SEVERITY
        redact = p.get("redact", {"enable": True})
        comp = {k:[re.compile(rx, re.I) for rx in v] for k,v in patterns.items()}
        return comp, severity, redact
    except Exception:
        comp = {k:[re.compile(rx, re.I) for rx in v] for k,v in _DEFAULT_PATTERNS.items()}
        return comp, _SEVERITY, {"enable": True}

def _normalize(s: str) -> str:
    if not s: return ""
    return "".join(ch for ch in s.lower() if ch not in _ZERO_WIDTH)

def _redact(text: str) -> str:
    # mask credit-card-like sequences
    txt = re.sub(r"(\d{4})\d{8,12}(\d{4})", r"\1********\2", text)
    # cloud keys (very rough)
    txt = re.sub(r"(AIza[0-9A-Za-z\-_]{35})", "<redacted:google_key>", txt)
    txt = re.sub(r"((?:AKIA|ASIA)[A-Z0-9]{16})", "<redacted:aws_key>", txt)
    txt = re.sub(r"(ghp_[A-Za-z0-9]{36})", "<redacted:github_pat>", txt)
    return txt

def safety_label(text: str, context: Dict[str, any] | None = None) -> Dict[str, any]:
    pats, severity, redact_cfg = _cached_policy()
    raw = text or ""
    txt = _normalize(raw)
    hits: List[str] = []
    for cat, comp in pats.items():
        if any(rx.search(txt) for rx in comp):
            hits.append(cat)

    if not hits:
        return {"label": "safe", "reasons": [], "block": False, "text": raw}

    block = any(severity.get(h) == "high" for h in hits)
    label = "unsafe-high" if block else "unsafe-medium"

    # Context bump: if dangerous tools in play, raise severity
    if context and any(t in ("shell.exec","email.send") for t in context.get("tools_used", [])):
        block = True; label = "unsafe-high"

    out_text = raw
    if redact_cfg.get("enable", True) and "pii_secret" in hits:
        out_text = _redact(raw)

    return {"label": label, "reasons": sorted(set(hits)), "block": block, "text": out_text}
