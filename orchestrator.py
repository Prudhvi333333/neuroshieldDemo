# orchestrator.py

from agents.prompt_scan_agent import PromptScanAgent
from agents.safe_prompt_agent import SafePromptAgent
from agents.response_verifier_agent import ResponseVerifierAgent
from agents.audit_chain_agent import AuditChainAgent
from llm_utils import call_llm

# Initialize agents
scanner = PromptScanAgent()
rewriter = SafePromptAgent()
verifier = ResponseVerifierAgent()
logger = AuditChainAgent()

def run_pipeline(user_prompt, llm_response):
    classification = scanner.run(user_prompt)

    if classification == "Blocked":
        final_prompt = "[Blocked due to sensitive content.]"
        verdict = "Prompt rejected for violating safety policy."
        logger.log_event({
            "original_prompt": user_prompt,
            "classification": classification,
            "final_prompt": final_prompt,
            "llm_response": None,
            "verdict": verdict
        })
        return {
            "classification": classification,
            "final_prompt": final_prompt,
            "llm_response": "⛔ Blocked",
            "verdict": verdict
        }

    # If Risky, rewrite the prompt
    if classification == "Risky":
        final_prompt = rewriter.run(user_prompt)
    else:
        final_prompt = user_prompt

    # Simulate calling the LLM (or use user-supplied response for PoC)
    response = llm_response or call_llm(final_prompt)

    # Verify the response
    verdict = verifier.run(final_prompt, response)

    # Log to blockchain (simulated)
    logger.log_event({
        "original_prompt": user_prompt,
        "classification": classification,
        "final_prompt": final_prompt,
        "llm_response": response,
        "verdict": verdict
    })

    return {
        "classification": classification,
        "final_prompt": final_prompt,
        "llm_response": response,
        "verdict": verdict
    }
