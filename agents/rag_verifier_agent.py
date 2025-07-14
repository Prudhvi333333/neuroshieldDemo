# agents/rag_verifier_agent.py

from .base_agent import BaseAgent
import json

class RAGVerifierAgent(BaseAgent):
    def __init__(self):
        super().__init__("RAGVerifierAgent")
        # TODO: Initialize vector store with your documents
        # self.vectorstore = Chroma(embedding_function=OpenAIEmbeddings())

    def run(self, prompt: str, response: str) -> dict:
        system_msg = (
            "You are a RAG-enhanced fact checker. "
            "Use your knowledge to verify if the response is factual. "
            "Return JSON with 'verdict' and 'confidence'."
        )

        user_msg = (
            f"Prompt: {prompt}\n\n"
            f"Response to verify: {response}\n\n"
            "Check factual accuracy and return:\n"
            "{ \"verdict\": \"Factual/Unverifiable/Hallucinated\", \"confidence\": 0.0-1.0 }"
        )

        result = self.reason(user_msg, system_msg)
        try:
            import re
            match = re.search(r"\{.*?\}", result, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            print("RAGVerifierAgent JSON parse error:", e)
        
        return {"verdict": "Unverifiable", "confidence": 0.0} 