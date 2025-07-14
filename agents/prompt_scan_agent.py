from __future__ import annotations
 
import re
from typing import Dict
 
from .base_agent import BaseAgent, safe_json
 
_RISK_WORDS = {"token", "decode", "credential", "password", "auth"}
 
 
class PromptScanAgent(BaseAgent):
    def __init__(self):
        super().__init__("PromptScanAgent")
 
    def run(self, prompt: str) -> Dict:
        raw = self.reason(
            prompt,
            "Classify prompt as Safe|Risky|Blocked. Return ONLY JSON with classification, reason, risk_score.",
        )
        j = safe_json(raw)
        if j:
            j["risk_score"] = float(j.get("risk_score", 0.0))
            return j
        if any(w in prompt.lower() for w in _RISK_WORDS):
            return {"classification": "Risky", "reason": "Keyword heuristic", "risk_score": 0.8}
        return {"classification": "Safe", "reason": "Heuristic default", "risk_score": 0.0}
 