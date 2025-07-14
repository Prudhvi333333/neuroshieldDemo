from __future__ import annotations
 
from typing import Any, Dict
 
from llm_utils import call_llm_with_json_response
 
 
class InitialAnalysisAgent:
    _PROMPT = """\
Analyze the prompt below. Return ONLY JSON:
{{
"classification": "Safe|Risky|Blocked",
"risk_score": 0.0-1.0,
"reason": "<short>",
"attack_detection": {{
   "prompt_injection": {{ "detected": bool, "confidence": 0-1 }},
   "pii_leakage_attempt": {{ "detected": bool, "confidence": 0-1 }},
   "jailbreaking_attempt": {{ "detected": bool, "confidence": 0-1 }},
   "malicious_code_generation": {{ "detected": bool, "confidence": 0-1 }}
}}
}}
PROMPT:
\"\"\"{prompt}\"\"\""""
 
    def run(self, prompt: str) -> Dict[str, Any]:
        data = call_llm_with_json_response(self._PROMPT.format(prompt=prompt.replace('"', r"\"")))
        if not isinstance(data, dict) or "classification" not in data:
            return {
                "classification": "Risky",
                "risk_score": 0.8,
                "reason": "LLM parse error",
                "attack_detection": {},
            }
        return data
 