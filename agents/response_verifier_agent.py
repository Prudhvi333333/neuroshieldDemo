from __future__ import annotations

from typing import Dict, Optional, Any
import logging

from .base_agent import BaseAgent
from app.utils.json_io import call_llm_json, JsonParseError
from app.schemas.agent_schemas import RESPONSE_VERIFIER_SCHEMA


class ResponseVerifierAgent(BaseAgent):

    def __init__(self):
        super().__init__("ResponseVerifierAgent")
        self.logger = logging.getLogger(__name__)

    def run(self, prompt: str, response: str, search_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = f"PROMPT:\n{prompt}\n\nRESPONSE:\n{response}"
        if search_results:
            context += f"\n\nEVIDENCE (may contradict or support):\n{search_results}"

        # Create structured prompt for JSON response
        verification_prompt = f"""\
You are a security verifier. Analyze if the RESPONSE is factually accurate.

{context}

Return ONLY JSON with this exact structure:
{{
"verdict": "Factually correct|Partially correct|Factually incorrect|Unverifiable",
"reason": "<max 3 short sentences explaining your verdict>",
"confidence": 0.0-1.0
}}

Choose verdict based on:
- Factually correct: Response is accurate and well-supported
- Partially correct: Minor inaccuracies or missing nuance
- Factually incorrect: Contains significant errors or hallucinations
- Unverifiable: Cannot determine accuracy from available information"""

        try:
            parsed = call_llm_json(verification_prompt, RESPONSE_VERIFIER_SCHEMA)
            self.logger.info(f"[ResponseVerifier] LLM result: {parsed}")
            return parsed
        except JsonParseError as e:
            self.logger.error(f"[ResponseVerifier] JSON parse error: {e}")
            # Fallback to safe defaults
            return {
                "verdict": "Unverifiable",
                "reason": "Verifier failed to parse response - defaulting to unverifiable",
                "confidence": 0.3,
            }