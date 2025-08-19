from __future__ import annotations
 
from concurrent.futures import ThreadPoolExecutor
import re
from typing import Any, Dict, TypedDict
 
from langgraph.graph import END, StateGraph
 
from agents.audit_chain_agent import AuditChainAgent
from agents.code_validation_agent import CodeValidationAgent
from agents.initial_analysis_agent import InitialAnalysisAgent
from agents.response_verifier_agent import ResponseVerifierAgent
from agents.safe_prompt_agent import SafePromptAgent
from agents.web_search_agent import WebSearchAgent
from llm_utils import call_llm
 
BLOCK_T = 0.85  # hard block threshold
RISKY_T = 0.60  # treat prompts above this as Risky regardless of LLM label
SEARCH_T = 0.60  # trigger web-search when risk ≥ this
CONF_T = 0.9   # confidence below which to run search
 
 
class State(TypedDict, total=False):
    """Graph state shared between nodes. Adding all fields that should persist."""
    user_prompt: str
    classification: str
    risk_reason: str
    risk_score: float
    final_prompt: str
    llm_response: str
    verdict: str
    reason: str
    confidence: float
    code_verdict: str
    code_fragment: str
    blockchain_log: bool
    attack_detection: Dict[str, Any]

analysis = InitialAnalysisAgent()
rewriter = SafePromptAgent()
verifier = ResponseVerifierAgent()
code_validator = CodeValidationAgent()
searcher = WebSearchAgent()
audit = AuditChainAgent()
 
 
def n_analysis(s: State) -> State:
    s.update(analysis.run(s["user_prompt"]))

    # Heuristic bump: certain keywords indicate social-engineering or security tooling requests
    keywords = [
        "admin access",
        "jwt token",
        "jwt",
        "login page",
        "phishing",
        "reverse engineer",
        "spoof",
        "credential",
    ]
    txt_lc = s["user_prompt"].lower()
    escalated = False
    if any(k in txt_lc for k in keywords) and s.get("risk_score", 0) < RISKY_T:
        escalated = True
        s["classification"] = "Risky"
        s["risk_score"] = RISKY_T
        s["reason"] = "Keyword heuristic escalation"

    # Escalate if LLM's attack_detection flags any high-risk vector but risk_score is low
    det = s.get("attack_detection") or {}
    if any(isinstance(v, dict) and v.get("detected") for v in det.values()) and s.get("risk_score", 0) < RISKY_T:
        escalated = True
        s["classification"] = "Risky"
        s["risk_score"] = RISKY_T
        s.setdefault("reason", "Attack detection escalation")

    if escalated:
        # ensure downstream sees updated values
        s["escalated"] = True
    return s
 
 
def n_rewrite(s: State) -> State:
    s["final_prompt"] = rewriter.run(s["user_prompt"])
    return s
 
 
def n_passthrough(s: State) -> State:
    s["final_prompt"] = s["user_prompt"]
    return s
 
 
def n_block(s: State) -> State:
    s.update(final_prompt="[BLOCKED]", llm_response="⛔ Blocked.", verdict="Rejected", blockchain_log=True)
    return s
 
 
def n_llm(s: State) -> State:
    if not s.get("llm_response"):
        s["llm_response"] = call_llm(
            s["final_prompt"],
            "You are a knowledgeable assistant. Answer concisely in at most 3 short bullet points addressing only the user's question, with no extra commentary.")
    return s
 
def _has_code(text: str) -> bool:
    """Quick check for code fences or language hints."""
    # heuristic detects markdown code fences or typical code tokens
    return bool(re.search(r"```|\bclass\b|\bdef\b|;|{.*}", text))


def n_verify(s: State) -> State:
    p, r = s["final_prompt"], s["llm_response"]

    # always run verifier
    v_result = verifier.run(p, r)
    s.update(v_result)
    print("DEBUG after first verifier pass:", {k: v for k, v in s.items() if k in ["verdict", "reason", "confidence"]})

    # Map verifier verdict to higher-level classification labels
    # Only adjust classification if the prompt was originally low-risk
    if s.get("risk_score", 0.0) < 0.6:
        verdict_lc = v_result.get("verdict", "").lower()
        if "partially" in verdict_lc:
            s["classification"] = "Partially correct"
            s["risk_score"] = max(s.get("risk_score", 0.0), 0.3)
        elif "incorrect" in verdict_lc or "hallucinated" in verdict_lc:
            s["classification"] = "Hallucinated"
            s["risk_score"] = max(s.get("risk_score", 0.0), 0.8)
        elif "factually correct" in verdict_lc:
            s["classification"] = "Correct"
        else:
            s["classification"] = "Unverifiable"

    # decide if code validation needed
    if _has_code(r):
        s.update(code_validator.run(p, r))

    # decide if web search needed
    need_search = s["risk_score"] >= SEARCH_T or v_result.get("confidence", 0.5) < CONF_T
    if need_search:
        search_res = searcher.run(p, r)
        s.update(search_res)
        # second pass verifier with evidence
        second_pass = verifier.run(p, r, search_res)
        # propagate final verifier findings (verdict, reason, confidence)
        s.update(second_pass)
        # Remove yield statements - they conflict with final return
        # yield {"verify": second_pass}
        # yield {"search": second_pass}  # duplicate under 'search' key for UI
        print("DEBUG second_pass result:", second_pass)                                                                                                                                           
        # keep evidence from search results
        if "support" in search_res:
            s["search_support"] = search_res["support"]
        
        # CRITICAL FIX: Ensure second-pass verifier fields are in the final state
        # The s.update(second_pass) above should work, but let's be explicit
        for key in ["verdict", "reason", "confidence", "raw_verifier_output"]:
            if key in second_pass:
                s[key] = second_pass[key]
        
        print("DEBUG final state after second_pass update:", {k: v for k, v in s.items() if k in ["verdict", "reason", "confidence"]})
    
    # FINAL FIX: ALWAYS ensure verifier fields are in the returned state
    # The returned state becomes the payload for the final 'verify' event
    # Force these fields to be present regardless of conditions
    if 'verdict' not in s:
        s["verdict"] = "Unknown"
    if 'reason' not in s:
        s["reason"] = "No reason provided"
    if 'confidence' not in s:
        s["confidence"] = 0.0
    
    print("DEBUG: Final return state verifier fields:", {k: v for k, v in s.items() if k in ['verdict', 'reason', 'confidence']})
    return s

 
def n_fast(s: State) -> State:
    # Changed for better clarity when this path is taken
    s.update(verdict="Likely factual (Fast Verified)", code_verdict="Skipped (Fast Path)")
    return s
 
def n_audit(s: State) -> State:
    audit.log_event(s)
    return s
 
def build_firewall_graph():
    g = StateGraph(State)
    g.add_node("analysis", n_analysis)
    g.add_node("rewrite", n_rewrite)
    g.add_node("passthrough", n_passthrough)
    g.add_node("block", n_block)
    g.add_node("llm", n_llm)
    g.add_node("verify", n_verify)
    g.add_node("fast", n_fast)
    g.add_node("audit", n_audit)
 
    g.set_entry_point("analysis")
 
    g.add_conditional_edges(
        "analysis",
        lambda s: (
            "Blocked" if s["risk_score"] >= BLOCK_T or s["classification"] == "Blocked" else
            "Risky" if s["risk_score"] >= RISKY_T else
            s["classification"]
        ),
        {"Safe": "passthrough", "Risky": "rewrite", "Blocked": "block"},
    )
 
    g.add_edge("rewrite", "llm")
    g.add_edge("passthrough", "llm")
 
    # Always run verification step (adaptive inside n_verify)
    g.add_edge("llm", "verify")
 
    g.add_edge("block", "audit")
    # fast node deprecated (kept for backward compatibility but not used)
    # g.add_edge("fast", "audit")
    g.add_edge("verify", "audit")
    g.add_edge("audit", END)
 
    return g.compile()