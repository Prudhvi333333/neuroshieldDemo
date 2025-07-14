# langgraph_core/firewall_graph.py
 
from __future__ import annotations
 
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, TypedDict
 
from langgraph.graph import END, StateGraph
 
from agents.audit_chain_agent import AuditChainAgent
from agents.code_validation_agent import CodeValidationAgent
from agents.initial_analysis_agent import InitialAnalysisAgent
from agents.response_verifier_agent import ResponseVerifierAgent
from agents.safe_prompt_agent import SafePromptAgent
from agents.web_search_agent import WebSearchAgent
from llm_utils import call_llm
 
BLOCK_T = 0.85
FAST_T = 0.30
 
 
class State(TypedDict, total=False):
    user_prompt: str
    classification: str
    risk_reason: str
    risk_score: float
    final_prompt: str
    llm_response: str
    verdict: str
    code_verdict: str
    code_fragment: str
    blockchain_log: bool
    attack_detection: Dict[str, Any]
    web_search_results: Dict[str, Any]
 # <--- IMPORTANT: Ensure this field exists in your State TypedDict
 
 
analysis = InitialAnalysisAgent()
rewriter = SafePromptAgent()
verifier = ResponseVerifierAgent()
code_validator = CodeValidationAgent()
searcher = WebSearchAgent()
audit = AuditChainAgent()
 
 
def n_analysis(s: State) -> State:
    s.update(analysis.run(s["user_prompt"]))
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
        s["llm_response"] = call_llm(s["final_prompt"])
    return s
 
 
def n_verify(s: State) -> State:
    p, r = s["final_prompt"], s["llm_response"]

    with ThreadPoolExecutor(max_workers=3) as ex:
        # Submit tasks that can run in parallel
        search_future = ex.submit(searcher.run, p, r)
        code_validation_future = ex.submit(code_validator.run, p, r)

        # Retrieve search results first, as verifier needs them
        search_results_update_dict = search_future.result() # This blocks and waits
        s.update(search_results_update_dict) # Update the state with web_search_results, assumedly has key 'web_search_results'

        # Now run verifier, explicitly passing the search results
        verifier_results_update_dict = verifier.run(p, r, search_results=s.get("web_search_results"))
        s.update(verifier_results_update_dict)

        # Retrieve and update state with code validation results
        s.update(code_validation_future.result())

 
 
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
        lambda s: "Blocked" if s["classification"] == "Blocked" or s["risk_score"] >= BLOCK_T else s["classification"],
        {"Safe": "passthrough", "Risky": "rewrite", "Blocked": "block"},
    )
 
    g.add_edge("rewrite", "llm")
    g.add_edge("passthrough", "llm")
 
    g.add_conditional_edges(
        "llm",
        lambda s: "fast" if s["risk_score"] < FAST_T else "verify",
        {"fast": "fast", "verify": "verify"},
    )
 
    g.add_edge("block", "audit")
    g.add_edge("fast", "audit")
    g.add_edge("verify", "audit")
    g.add_edge("audit", END)
 
    return g.compile()
