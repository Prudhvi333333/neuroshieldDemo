# agents/web_search_agent.py

from .base_agent import BaseAgent

class WebSearchAgent(BaseAgent):
    def __init__(self):
        super().__init__("WebSearchAgent")

    def run(self, prompt: str, response: str) -> dict:
        system_msg = (
            "You are a fact checker who can use simulated search. "
            "Use your internal knowledge to validate the response content. "
            "If you cannot verify, reply with: { 'verdict': 'Unverifiable', 'support': 'No public evidence found.' }"
        )

        user_msg = (
            f"Prompt: {prompt}\n\n"
            f"Response to fact-check: {response}\n\n"
            "Reply with a JSON like: \n"
            "{ 'verdict': 'Likely factual', 'support': 'Matches well-known facts available publicly' }"
        )

        result = self.reason(user_msg, system_msg)
        try:
            import json, re
            # Simple JSON extraction - find the first { and last }
            start = result.find('{')
            end = result.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = result[start:end+1]
                return json.loads(json_str)
        except Exception as e:
            print("WebSearchAgent JSON parse error:", e)
        return { 'verdict': 'Unverifiable', 'support': 'Failed to parse reasoning.' }
