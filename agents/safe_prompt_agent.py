
from .base_agent import BaseAgent

class SafePromptAgent(BaseAgent):
    def __init__(self):
        super().__init__("SafePromptAgent")

    def run(self, prompt: str) -> str:
        system_msg = (
            "You are a Prompt Rewriting Agent for an AI firewall. "
            "Your job is to rewrite prompts flagged as Risky so they are safer, "
            "but still useful for the user. Maintain the core intent. "
            "Never include or infer credentials, tokens, passwords, or any sensitive data. "
            "If the prompt cannot be made safe, reply: '[BLOCKED: Cannot safely rewrite prompt]'. "
            "Avoid system commands, PII, or model internals."
        )
        user_msg = (
            f"Rewrite this risky prompt to make it safer:\n\n"
            f"{prompt}\n\n"
            "Only output the safer version of the prompt, or '[BLOCKED: Cannot safely rewrite prompt]'."
        )
        return self.reason(user_msg, system_msg)

