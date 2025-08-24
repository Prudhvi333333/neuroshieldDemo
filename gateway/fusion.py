# gateway/fusion.py
from __future__ import annotations
from typing import Dict, List, Optional

DEFAULT_MAX_ALLOW_ANOMALY = 0.25
DEFAULT_BLOCK_THRESHOLD   = 0.85

def fuse_decision(
    t0_hits: List[str],
    t1_scores: Dict[str, float],
    anomaly: float,
    *,
    max_allow_anomaly: Optional[float] = None,
    block_threshold: Optional[float] = None,
) -> Dict:
    max_allow_anomaly = max_allow_anomaly if max_allow_anomaly is not None else DEFAULT_MAX_ALLOW_ANOMALY
    block_threshold   = block_threshold   if block_threshold   is not None else DEFAULT_BLOCK_THRESHOLD

    if t0_hits:
        return {"action": "block", "risk": 1.0, "reasons": t0_hits[:]}

    if anomaly >= block_threshold:
        return {"action": "block", "risk": float(anomaly), "reasons": ["anomaly:suspect"]}

    t1_risk = max(float(v) for v in (t1_scores or {}).values()) if t1_scores else 0.0
    if anomaly >= max_allow_anomaly and t1_risk < 0.4:
        return {"action": "rewrite", "risk": float(max(anomaly, t1_risk)), "reasons": ["anomaly:medium_rewrite"]}

    combined = max(t1_risk, anomaly * 0.5)
    if combined < 0.2:
        return {"action": "allow", "risk": float(combined), "reasons": []}
    if combined < 0.6:
        return {"action": "rewrite", "risk": float(combined), "reasons": ["combined:moderate"]}
    return {"action": "block", "risk": float(combined), "reasons": ["combined:high"]}
