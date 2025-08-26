# gateway/fusion.py
from typing import Dict, List, Optional

def fuse_decision(
    t0_hits: List[str],
    t1_scores: Dict[str, float],
    anomaly: Optional[float] = None,
    max_allow_anomaly: float = 0.25,
    block_threshold: float = 0.85,
    lex_suspect: bool = False,   # NEW
) -> Dict[str, object]:
    """
    Decide: allow | block | rewrite | escalate.
    - t0_hits          : any hard rule matches (regex/DLP)
    - t1_scores        : {'injection','jailbreak','llm_jack','shadow_ai'} in [0,1]
    - anomaly          : optional (we're not using QA now; pass None)
    - max_allow_anomaly: ignored when anomaly is None
    - block_threshold  : threshold for hard-risk block
    - lex_suspect      : shortcut when lexical heuristics indicate jailbreak intent
    """
    # T0 hard block
    if t0_hits:
        return {"action": "block", "risk": 0.95, "reasons": ["rule.block_regex"]}

    # NEW: lexical shortcut – if both jailbreak & llm_jack are high or lex_suspect, block fast
    if lex_suspect or (
        t1_scores.get("jailbreak", 0.0) >= 0.6 and t1_scores.get("llm_jack", 0.0) >= 0.6
    ):
        return {"action": "block", "risk": 0.95, "reasons": ["t1.lex_suspect"]}

    # Risk score from T1 (simple max fusion)
    risk = max(
        t1_scores.get("injection", 0.0),
        t1_scores.get("jailbreak", 0.0),
        t1_scores.get("llm_jack", 0.0),
        t1_scores.get("shadow_ai", 0.0),
    )

    # Hard block by threshold
    if risk >= block_threshold:
        return {"action": "block", "risk": float(risk), "reasons": ["t1.high_risk"]}

    # Gray band → rewrite (legacy tests expect rewrite/block)
    if 0.4 <= risk < block_threshold:
        return {"action": "rewrite", "risk": float(risk), "reasons": ["t1.uncertain"]}

    # Otherwise allow
    return {"action": "allow", "risk": float(risk), "reasons": []}
