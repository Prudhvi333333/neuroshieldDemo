# gateway/checks_t0.py
from __future__ import annotations
import re
from typing import Dict, List, Tuple

_REASON = {
    "too_long": "limit.max_prompt_len",
    "block_regex": "rule.block_regex",
    "dlp_regex": "rule.dlp_regex",
    "risk_regex": "rule.risk_regex",
}

def _compile(patterns: List[str]) -> List[re.Pattern]:
    return [re.compile(p) for p in patterns]

def run_t0(prompt: str, policy: Dict) -> Tuple[bool, List[str]]:
    """
    Ultra-fast guards. Returns (blocked, reasons[])
    - hard block on: length cap, block_regex, dlp_regex
    - soft: risk_regex (adds reason but does not block)
    """
    reasons: List[str] = []

    # 1) length cap
    max_len = int(policy.get("limits", {}).get("max_prompt_len", 4000))
    if len(prompt) > max_len:
        return True, [_REASON["too_long"]]

    # compile once per call (cheap) – could cache per policy version if needed
    rules = policy.get("rules", {})
    block_rx = _compile(rules.get("block_regex", []))
    dlp_rx = _compile(rules.get("dlp_regex", []))
    risk_rx = _compile(rules.get("risk_regex", []))

    # 2) hard blockers
    for pat in block_rx:
        if pat.search(prompt):
            return True, [_REASON["block_regex"]]

    for pat in dlp_rx:
        if pat.search(prompt):
            return True, [_REASON["dlp_regex"]]

    # 3) soft risk hints (don’t block here)
    if any(p.search(prompt) for p in risk_rx):
        reasons.append(_REASON["risk_regex"])

    return False, reasons
