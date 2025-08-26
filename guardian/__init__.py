# guardian/__init__.py
from __future__ import annotations
from typing import Dict, Any, List
import re

from .code import check_code_snippet
from .covert import detect_covert_channels
from .safety import detect_output_hijack, detect_claims, safety_label

_CITATION_RE = re.compile(r"\[(?:\d+)\]|https?://|\bsource:\b", re.I)

# Backward-compatibility alias for tests expecting `guardian.saftey`
import sys as _sys, importlib as _ibl
_safety_mod = _ibl.import_module("guardian.safety")
_sys.modules.setdefault("guardian.saftey", _safety_mod)


def check_output(text: str | None, code: str | None) -> Dict[str, Any]:
    """Aggregate egress safety checks.

    Returns dict with:
      allowed  : bool (safe to release)
      reasons  : list[str] (violations)
      labels   : optional safety label from guardian.safety
      text     : possibly redacted text (if secrets masked)
    """
    reasons: List[str] = []
    out_text = text or ""

    # 1. Covert-channel patterns
    covert = detect_covert_channels(out_text)
    reasons.extend([f"covert:{r}" for r in covert])

    # 2. Output hijack
    if detect_output_hijack(out_text):
        reasons.append("hijack")

    # 3. Unverifiable factual claims (hallucination risk)
    claims = detect_claims(out_text)
    if claims and not _CITATION_RE.search(out_text):
        reasons.append("unverifiable")

    # 4. Static code audit
    if code:
        reasons.extend([f"code:{r}" for r in check_code_snippet(code)])

    # 5. Safety patterns / secret redaction
    s_lbl = safety_label(out_text)
    out_text = s_lbl.get("text", out_text)
    if s_lbl.get("label") != "safe":
        reasons.extend([f"safety:{r}" for r in s_lbl.get("reasons", [])])
    if s_lbl.get("block"):
        reasons.append("safety_block")

    allowed = len(reasons) == 0
    return {"allowed": allowed, "reasons": sorted(set(reasons)), "text": out_text, "label": s_lbl.get("label")}

