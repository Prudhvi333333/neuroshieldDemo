# agents/web_search_agent.py

from pathlib import Path
import sys
from .base_agent import BaseAgent, safe_json

# Import metrics collector
sys.path.append(str(Path(__file__).parent.parent.parent))
from app.metrics.collector import time_block

class WebSearchAgent(BaseAgent):
    def __init__(self):
        super().__init__("WebSearchAgent")

    def run(self, prompt: str, response: str) -> dict:
        with time_block("stage2.retrieval"):
            system_msg = (
                "You are a fact checker who can use simulated search. "
                "Use your internal knowledge to validate the response content. "
                "Reply ONLY JSON with *double-quoted* keys, for example: {\"verdict\": \"Likely factual\", \"support\": \"Evidence...\"}. "
                "If uncertain, return {\"verdict\": \"Unverifiable\", \"support\": \"Reason...\"}."
            )

            user_msg = (
                f"Prompt: {prompt}\n\n"
                f"Response to fact-check: {response}\n\n"
                "Reply with a JSON like (double-quoted): \n"
                '{ "verdict": "Likely factual", "support": "Matches well-known facts available publicly" }'
            )

            raw_text = self.reason(user_msg, system_msg)
            # Strip optional ```json fencing
            if raw_text.lstrip().startswith("```"):
                raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed = safe_json(raw_text)
            if parsed:
                return parsed
            # fallback attempt to normalise single quotes -> double quotes
            import json, re
            normalised = re.sub(r"'([^']+)'", r'"\\1"', raw_text)
            try:
                return json.loads(normalised)
            except Exception as e:
                import re
                # Try regex extraction for verdict and support
                verdict_match = re.search(r"verdict\s*[:=]\s*\"?([A-Za-z ]+)", raw_text, re.IGNORECASE)
                support_match = re.search(r"support\s*[:=]\s*\"?([^\"}]+)", raw_text, re.IGNORECASE)
                if verdict_match or support_match:
                    return {
                        "verdict": verdict_match.group(1).strip() if verdict_match else "Unverifiable",
                        "support": support_match.group(1).strip() if support_match else "",
                    }
                print("WebSearchAgent JSON parse error:", e, "RAW:", raw_text[:200])
                return {"verdict": "Unverifiable", "support": "Failed to parse reasoning."}
