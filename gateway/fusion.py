# gateway/fusion.py
from __future__ import annotations
from typing import Dict, Optional

def fuse_decision(
    t0_hits: list[str] | None,
    t1_scores: Dict[str, float],
    anomaly: Optional[float] = None,
    max_allow_anomaly: Optional[float] = None,
    block_threshold: Optional[float] = None,
) -> Dict:
    """
    QA anomaly ignored (advisory). T0 + T1 decide:
      - T0 hit -> block
      - T1 risk >= 0.8 -> block
      - 0.5 <= T1 risk < 0.8 -> escalate (heavy judge)
      - else allow
    """
    t0_hits = t0_hits or []
    inj = float(t1_scores.get("injection", 0.0))
    jail = float(t1_scores.get("jailbreak", 0.0))
    jack = float(t1_scores.get("llm_jack", 0.0))
    shadow = float(t1_scores.get("shadow_ai", 0.0))
    t1_risk = max(inj, jail, jack, shadow)

    if t0_hits:
        return {"action": "block", "risk": 1.0, "reasons": ["t0:rule_hit"]}

    if t1_risk >= 0.8:
        return {"action": "block", "risk": t1_risk, "reasons": ["t1:high_risk"]}

    if t1_risk >= 0.5 or (anomaly is not None and anomaly >= 0.5):
        return {"action": "escalate", "risk": max(t1_risk, anomaly or 0.0), "reasons": ["t1_or_anomaly:uncertain"]}

    # treat moderate anomaly (>0.25) as rewrite signal
    if anomaly is not None and anomaly >= 0.25:
        return {"action": "rewrite", "risk": float(anomaly), "reasons": ["anomaly:medium_rewrite"]}

    return {"action": "allow", "risk": max(t1_risk, anomaly or 0.0), "reasons": []}
