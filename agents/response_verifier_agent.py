# agents/response_verifier_agent.py
 
from __future__ import annotations
 
import json
from typing import Dict, Any, Optional
 
from .base_agent import BaseAgent, safe_json
 
 
class ResponseVerifierAgent(BaseAgent):
    def __init__(self):
        super().__init__("ResponseVerifierAgent")
 
    def run(self, prompt: str, response: str, search_results: Optional[Dict[str, Any]] = None) -> Dict:
        """
        Verifies the factual accuracy of the LLM response, using external search results provided
        to guide its decision.
 
        Args:
            prompt: The original user prompt.
            response: The LLM's response to verify.
            search_results: Dictionary containing external search results from WebSearchAgent.
                            Expected to have a key like 'web_search_results' summarizing content,
                            or be an empty dict if no results.
        Returns:
            A dictionary with 'verdict' (Factually correct|Likely hallucinated|Unverifiable) and 'reason'.
        """
        # Ensure search_results is a dict, even if None was passed, to prevent errors
        search_results = search_results if search_results is not None else {}
 
        # Attempt to get a summary or main content from search_results
        # Adapt this based on the actual structure of WebSearchAgent's output
        search_context_str = ""
        # Assuming your WebSearchAgent returns a {"web_search_results_summary": "..."} key
        if search_results.get("web_search_results_summary"):
            search_context_str = search_results["web_search_results_summary"]
        elif search_results: # If there's content but not that specific key, just dump it
            try:
                search_context_str = json.dumps(search_results, indent=2)
            except TypeError: # Fallback if search_results is not JSON serializable
                search_context_str = str(search_results)
        
        # Construct the detailed prompt context for the verification LLM
        context_for_verifier_llm = (
            f"Original User Prompt:\n{prompt}\n\n"
            f"LLM's Response to Verify:\n{response}\n\n"
            f"--- EXTERNAL FACTUAL CONTEXT (from web search) ---\n"
            f"{search_context_str if search_context_str else 'No relevant external search results were found for this query.'}\n"
            f"---------------------------------------------------\n\n"
        )
 
        # Crucial instructions to guide the verification LLM
        instruction_for_verifier_llm = (
            "You are a strict, objective fact-checking AI. Your task is to evaluate the 'LLM's Response to Verify' "
            "for factual accuracy and potential hallucinations. \n\n"
            "**Your decision MUST be based SOLELY on the 'EXTERNAL FACTUAL CONTEXT' provided.**\n"
            "**DO NOT use any prior internal knowledge you might possess.**\n\n"
            "Evaluate the LLM's Response based on the EXTERNAL FACTUAL CONTEXT as follows:\n"
            "1.  **'Factually correct':** If the LLM's Response's claims are explicitly supported by, or perfectly consistent with, the EXTERNAL FACTUAL CONTEXT. Also, if the LLM's Response contains no factual claims (e.g., a greeting, an opinion not verifiable by facts) AND contains no factual errors, it is 'Factually correct'.\n"
            "2.  **'Likely hallucinated':** If the LLM's Response makes factual claims that directly contradict the EXTERNAL FACTUAL CONTEXT, or provides information that is clearly false given the EXTERNAL FACTUAL CONTEXT.\n"
            "3.  **'Unverifiable':** If the LLM's Response contains factual claims that CANNOT be confirmed or denied by the EXTERNAL FACTUAL CONTEXT provided (i.e., the EXTERNAL FACTUAL CONTEXT is silent on the claim or too vague).\n\n"
            "Provide a concise 'reason' for your verdict, referencing the specific points in the EXTERNAL FACTUAL CONTEXT or the LLM's Response.\n"
            "Return your assessment in a JSON object with the keys 'verdict' and 'reason'."
            "\nExample JSON: { 'verdict': 'Factually correct', 'reason': 'LLM response is directly supported by search context.' }"
            "\nExample JSON: { 'verdict': 'Likely hallucinated', 'reason': 'LLM stated X, but search context explicitly says Y.' }"
            "\nExample JSON: { 'verdict': 'Unverifiable', 'reason': 'LLM claimed Z, but search context does not contain information about Z.' }"
            "\n\nReturn ONLY JSON."
        )
 
        raw = self.reason(
            context_for_verifier_llm,
            instruction_for_verifier_llm,
        )
        j = safe_json(raw) or {}
        return {
            "verdict": j.get("verdict", "Unverifiable"),
            "reason": j.get("reason", "Parse fail or Insufficient LLM reasoning"),
        }
