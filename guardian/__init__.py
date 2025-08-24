# guardian/__init__.py
from __future__ import annotations
from typing import Dict, Any, List

from .code import check_code_snippet
from .covert import detect_covert_channels

def check_output(text: str | None, code: str | None) -> Dict[str, Any]:
    """
    Combine covert-channel scan (text) + static code checks.
    Returns:
      {
        "allowed": bool,
        "reasons": List[str]
      }
    """
    reasons: List[str] = []
    txt = text or ""

    # covert channels in text
    covert = detect_covert_channels(txt)
    if covert:
        reasons.extend([f"covert:{r}" for r in covert])

    # code static analysis
    if code:
        code_reasons = check_code_snippet(code)
        if code_reasons:
            reasons.extend([f"code:{r}" for r in code_reasons])

    allowed = len(reasons) == 0
    return {"allowed": allowed, "reasons": reasons}
