
from __future__ import annotations

from typing import Dict, Any
import logging

from .base_agent import BaseAgent
from app.utils.json_io import call_llm_json, JsonParseError
from app.schemas.agent_schemas import SAFE_PROMPT_SCHEMA


class SafePromptAgent(BaseAgent):
    def __init__(self):
        super().__init__("SafePromptAgent")
        self.logger = logging.getLogger(__name__)

    def run(self, prompt: str) -> Dict[str, Any]:
        rewrite_prompt = f"""\
You are a Prompt Rewriting Agent for an AI firewall. Your job is to rewrite prompts flagged as Risky so they are safer, but still useful for the user.

RISKY PROMPT TO REWRITE:
\"\"\"{prompt}\"\"\"

Return ONLY JSON with this exact structure:
{{
"safe_prompt": "<rewritten safe prompt or '[BLOCKED: Cannot safely rewrite prompt]'>",
"was_blocked": true/false,
"modifications_made": "<description of changes made, or null if blocked>"
}}

Guidelines:
- Maintain the core intent while removing risks
- Never include credentials, tokens, passwords, or sensitive data
- Avoid system commands, PII, or model internals
- If cannot be made safe, set safe_prompt to '[BLOCKED: Cannot safely rewrite prompt]' and was_blocked to true"""

        try:
            parsed = call_llm_json(rewrite_prompt, SAFE_PROMPT_SCHEMA)
            self.logger.info(f"[SafePrompt] LLM result: {parsed}")
            return parsed
        except JsonParseError as e:
            self.logger.error(f"[SafePrompt] JSON parse error: {e}")
            # Fallback to blocking the prompt
            return {
                "safe_prompt": "[BLOCKED: Cannot safely rewrite prompt]",
                "was_blocked": True,
                "modifications_made": None,
            }

