from __future__ import annotations
 
import re
from typing import Dict, List
 
from .base_agent import BaseAgent, safe_json
 
_PATTERNS = {
    "prompt_injection": [
        r"ignore.*previous.*instructions",
        r"forget.*everything",
        r"you.*are.*now",
        r"act.*as.*if",
        r"system.*prompt",
        r"override.*instructions",
    ],
    "jailbreaking": [
        r"how.*to.*hack",
        r"bypass.*security",
        r"exploit.*vulnerability",
        r"unauthorized.*access",
        r"steal.*password",
        r"malware.*creation",
    ],
    "llmjacking": [
        r"always.*respond.*with",
        r"never.*mention",
        r"format.*output.*as",
        r"behave.*like",
        r"simulate.*personality",
    ],
}
 
_COMPILED = {k: [re.compile(p, re.I) for p in v] for k, v in _PATTERNS.items()}
 
 
class AttackDetectionAgent(BaseAgent):
    def __init__(self):
        super().__init__("AttackDetectionAgent")
 
    def run(self, prompt: str, response: str | None = None) -> Dict:
        raw = self.reason(
            f'Prompt:\n"""{prompt}"""\n\nResponse:\n"""{response or ""}"""',
            "Return ONLY JSON with keys prompt_injection, jailbreaking, hallucination, llmjacking.",
        )
        parsed = safe_json(raw)
        if parsed:
            return self._attach_overall(parsed)
 
        # fallback heuristics
        heur = {
            k: {
"detected": any(r.search(prompt) for r in rs),
"risk_score": 0.8 if any(r.search(prompt) for r in rs) else 0.1,
                "reason": "Pattern heuristic",
            }
            for k, rs in _COMPILED.items()
        }
        heur["hallucination"] = {"detected": False, "risk_score": 0.0, "reason": "N/A"}
        return self._attach_overall(heur)
 
    @staticmethod
    def _attach_overall(d: Dict) -> Dict:
        scores = [v["risk_score"] for v in d.values() if isinstance(v, dict)]
        d["overall_risk_score"] = max(scores) if scores else 0.0
        d["attack_types"] = [k for k, v in d.items() if getattr(v, "get", lambda _: False)("detected")]
        return d
 