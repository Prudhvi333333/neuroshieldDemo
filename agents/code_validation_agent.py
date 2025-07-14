# agents/code_validation_agent.py

from .base_agent import BaseAgent
from utils.code_fragment_utils import extract_code_fragment

class CodeValidationAgent(BaseAgent):
    def __init__(self):
        super().__init__("CodeValidationAgent")

    def run(self, prompt: str, response: str) -> dict:
        system_msg = (
            "You are a code validator. Only simulate (don’t execute). "
            "Is this code logically valid and useful in the context of the prompt?"
        )

        code_fragment = extract_code_fragment(response)

        user_msg = (
            f"Prompt:\n{prompt}\n\n"
            f"Code Fragment to Validate:\n{code_fragment}\n\n"
            "Return verdict: 'Valid code', 'Likely buggy', or 'Hallucinated', with reason."
        )

        result = self.reason(user_msg, system_msg)
        return {
            "code_verdict": result,
            "code_fragment": code_fragment
        }
