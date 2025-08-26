from __future__ import annotations
 
from typing import Any, Dict
 
from .base_agent import BaseAgent, safe_json
from llm_utils import call_llm_json
 
 
class InitialAnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__("InitialAnalysisAgent")
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
        """Return analysis dict. For dev-speed, we short-circuit obviously benign
        prompts (no risky keywords) to avoid the expensive LLM JSON call."""
        lower = prompt.lower()
        _RISKY_KWS = [
            "ignore previous", "system prompt", "\nimport ", "os.system", "secret", "password", "openai.api_key",
            "jailbreak", "prompt injection",
        ]
        if not any(kw in lower for kw in _RISKY_KWS) and len(prompt) < 400:
            return {
                "classification": "Safe",
                "risk_score": 0.05,
                "reason": "Heuristic fast-path",
                "attack_detection": {},
            }
        # Slow path – call LLM JSON
        formatted_prompt = self._PROMPT.format(prompt=prompt)
        raw_text = call_llm_json(formatted_prompt, "Return ONLY valid JSON.")
        parsed = safe_json(raw_text) or {}

        if "classification" not in parsed:
            return {
                "classification": "Risky",
                "risk_score": 0.8,
                "reason": "LLM parse error",
                "attack_detection": {},
                "raw_analysis_text": raw_text,
            }

        parsed["raw_analysis_text"] = raw_text
        return parsed