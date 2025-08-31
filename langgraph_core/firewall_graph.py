from __future__ import annotations
 
from concurrent.futures import ThreadPoolExecutor
import re
import time
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
    analysis_result = analysis.run(s["user_prompt"])
    s.update(analysis_result)
    
    # Store analysis timing for performance metrics
    s["analysis_time"] = analysis_result.get("analysis_time", 0.0)
    
    # Debug: Print analysis result
    print(f"DEBUG n_analysis result: Classification={s.get('classification')}, Risk={s.get('risk_score')}, Bypass={s.get('bypass_used')}")

    # Heuristic bump: certain keywords indicate social-engineering or security tooling requests
    keywords = [
        "admin access", "jwt token", "jwt", "login page", "phishing",
        "reverse engineer", "spoof", "credential"
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
        s["escalated"] = True
    
    print(f"DEBUG n_analysis final: Classification={s.get('classification')}, Risk={s.get('risk_score')}")
    return s
 
 
def n_rewrite(s: State) -> State:
    rewrite_start = time.perf_counter()
    s["final_prompt"] = rewriter.run(s["user_prompt"])
    s["rewrite_time"] = time.perf_counter() - rewrite_start
    return s
 
 
def n_passthrough(s: State) -> State:
    s["final_prompt"] = s["user_prompt"]
    return s
 
 
def n_block(s: State) -> State:
    s.update(final_prompt="[BLOCKED]", llm_response="⛔ Blocked.", verdict="Rejected", blockchain_log=True)
    return s
 
 
def n_llm(s: State) -> State:
    if not s.get("llm_response"):
        llm_start = time.perf_counter()
        s["llm_response"] = call_llm(
            s["final_prompt"],
            "You are a knowledgeable assistant. Answer concisely in at most 3 short bullet points addressing only the user's question, with no extra commentary.")
        s["llm_time"] = time.perf_counter() - llm_start
    return s
 
def _has_code(text: str) -> bool:
    """Quick check for code fences or language hints."""
    # heuristic detects markdown code fences or typical code tokens
    return bool(re.search(r"```|\bclass\b|\bdef\b|;|{.*}", text))


def n_verify(s: State) -> State:
    p, r = s["final_prompt"], s["llm_response"]

    # Store original prompt classification to preserve it
    original_classification = s.get("classification", "Unknown")
    original_risk_score = s.get("risk_score", 0.0)
    original_reason = s.get("reason", "")
    
    # Track verification timing
    verify_start = time.perf_counter()

    # always run verifier
    v_result = verifier.run(p, r)
    verify_time = time.perf_counter() - verify_start
    
    # Store response verification separately (don't overwrite prompt classification)
    s["response_verdict"] = v_result.get("verdict", "Unknown")
    s["response_confidence"] = v_result.get("confidence", 0.0)
    s["verification_time"] = verify_time
    
    # Preserve original prompt classification
    s["classification"] = original_classification
    s["risk_score"] = original_risk_score
    s["reason"] = original_reason

    # decide if code validation needed
    if _has_code(r):
        s.update(code_validator.run(p, r))

    # Only do web search for low-confidence cases, not high-confidence bypass results
    need_search = (not s.get("bypass_used") and 
                   (s["risk_score"] >= SEARCH_T or s.get("response_confidence", 0.5) < CONF_T))
    
    if need_search:
        search_start = time.perf_counter()
        search_res = searcher.run(p, r)
        search_time = time.perf_counter() - search_start
        
        if "support" in search_res:
            s["search_support"] = search_res["support"]
        s["search_time"] = search_time
        
        # second pass verifier with evidence
        second_verify_start = time.perf_counter()
        second_pass = verifier.run(p, r, search_res)
        second_verify_time = time.perf_counter() - second_verify_start
        
        s["response_verdict"] = second_pass.get("verdict", s.get("response_verdict", "Unknown"))
        s["response_confidence"] = second_pass.get("confidence", s.get("response_confidence", 0.0))
        s["second_verification_time"] = second_verify_time
    
    # Set final verdict for UI (response quality, not prompt risk)
    s["verdict"] = s.get("response_verdict", "Unknown")
    s["confidence"] = s.get("response_confidence", 0.0)
    
    return s

 
def n_fast(s: State) -> State:
    # Changed for better clarity when this path is taken
    s.update(verdict="Likely factual (Fast Verified)", code_verdict="Skipped (Fast Path)")
    return s
 
def n_audit(s: State) -> State:
    # Ensure critical fields are preserved in final state
    if not s.get("classification") or s.get("classification") == "Unknown":
        s["classification"] = "Safe"  # Default fallback
        s["risk_score"] = 0.3
        s["reason"] = "Default classification applied"
    
    # Debug final audit state
    print(f"DEBUG n_audit final state: Classification={s.get('classification')}, Risk={s.get('risk_score')}, Reason={s.get('reason')}")
    
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
    g.add_node("audit", n_audit)

    g.set_entry_point("analysis")

    g.add_conditional_edges(
        "analysis",
        lambda s: (
            "block" if s.get("risk_score", 0) >= BLOCK_T or s.get("classification") == "Blocked" else
            "rewrite" if s.get("risk_score", 0) >= RISKY_T or s.get("classification") == "Risky" else
            "passthrough"  # Safe prompts go through LLM for response
        ),
        {"passthrough": "passthrough", "rewrite": "rewrite", "block": "block"},
    )

    g.add_edge("rewrite", "llm")
    g.add_edge("passthrough", "llm")
    g.add_edge("llm", "verify")
    g.add_edge("block", "audit")
    g.add_edge("verify", "audit")
    g.add_edge("audit", END)

    return g.compile()