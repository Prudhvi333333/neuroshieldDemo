# guardian/__init__.py
from __future__ import annotations
from typing import Dict, List, Optional

from .code import check_code_snippet
from .covert import detect_covert_channels

def check_output(text: str, code: Optional[str] = None) -> Dict[str, object]:
    """
    Combine covert channel scan on plain text and AST checks for code.
    Returns: {"allowed": bool, "reasons": List[str]}
    """
    reasons: List[str] = []
    # text covert channels
    if text:
        reasons.extend(detect_covert_channels(text))
    # code analysis
    if code:
        reasons.extend(check_code_snippet(code))
    # de-dup
    reasons = sorted(set(reasons))
    # simple policy: block if anything suspicious
    allowed = len(reasons) == 0
    return {"allowed": allowed, "reasons": reasons}

__all__ = ["check_output"]
