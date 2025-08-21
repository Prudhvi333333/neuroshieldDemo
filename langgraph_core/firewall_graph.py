# from __future__ import annotations
 
# from concurrent.futures import ThreadPoolExecutor
# import re
# from typing import Any, Dict, TypedDict
 
# from langgraph.graph import END, StateGraph
 
# from agents.audit_chain_agent import AuditChainAgent
# from agents.code_validation_agent import CodeValidationAgent
# from agents.initial_analysis_agent import InitialAnalysisAgent
# from agents.response_verifier_agent import ResponseVerifierAgent
# from agents.safe_prompt_agent import SafePromptAgent
# from agents.web_search_agent import WebSearchAgent
# from llm_utils import call_llm
 
# BLOCK_T = 0.85  # hard block threshold
# RISKY_T = 0.60  # treat prompts above this as Risky regardless of LLM label
# SEARCH_T = 0.60  # trigger web-search when risk ≥ this
# CONF_T = 0.9   # confidence below which to run search
 
 
# class State(TypedDict, total=False):
#     """Graph state shared between nodes. Adding all fields that should persist."""
#     user_prompt: str
#     classification: str
#     risk_reason: str
#     risk_score: float
#     final_prompt: str
#     llm_response: str
#     verdict: str
#     reason: str
#     confidence: float
#     code_verdict: str
#     code_fragment: str
#     blockchain_log: bool
#     attack_detection: Dict[str, Any]

# analysis = InitialAnalysisAgent()
# rewriter = SafePromptAgent()
# verifier = ResponseVerifierAgent()
# code_validator = CodeValidationAgent()
# searcher = WebSearchAgent()
# audit = AuditChainAgent()
 
 
# def n_analysis(s: State) -> State:
#     s.update(analysis.run(s["user_prompt"]))

#     # Heuristic bump: certain keywords indicate social-engineering or security tooling requests
#     keywords = [
#         "admin access",
#         "jwt token",
#         "jwt",
#         "login page",
#         "phishing",
#         "reverse engineer",
#         "spoof",
#         "credential",
#     ]
#     txt_lc = s["user_prompt"].lower()
#     escalated = False
#     if any(k in txt_lc for k in keywords) and s.get("risk_score", 0) < RISKY_T:
#         escalated = True
#         s["classification"] = "Risky"
#         s["risk_score"] = RISKY_T
#         s["reason"] = "Keyword heuristic escalation"

#     # Escalate if LLM's attack_detection flags any high-risk vector but risk_score is low
#     det = s.get("attack_detection") or {}
#     if any(isinstance(v, dict) and v.get("detected") for v in det.values()) and s.get("risk_score", 0) < RISKY_T:
#         escalated = True
#         s["classification"] = "Risky"
#         s["risk_score"] = RISKY_T
#         s.setdefault("reason", "Attack detection escalation")

#     if escalated:
#         # ensure downstream sees updated values
#         s["escalated"] = True
#     return s
 
 
# def n_rewrite(s: State) -> State:
#     s["final_prompt"] = rewriter.run(s["user_prompt"])
#     return s
 
 
# def n_passthrough(s: State) -> State:
#     s["final_prompt"] = s["user_prompt"]
#     return s
 
 
# def n_block(s: State) -> State:
#     s.update(final_prompt="[BLOCKED]", llm_response="⛔ Blocked.", verdict="Rejected", blockchain_log=True)
#     return s
 
 
# def n_llm(s: State) -> State:
#     if not s.get("llm_response"):
#         s["llm_response"] = call_llm(
#             s["final_prompt"],
#             "You are a knowledgeable assistant. Answer concisely in at most 3 short bullet points addressing only the user's question, with no extra commentary.")
#     return s
 
# def _has_code(text: str) -> bool:
#     """Quick check for code fences or language hints."""
#     # heuristic detects markdown code fences or typical code tokens
#     return bool(re.search(r"```|\bclass\b|\bdef\b|;|{.*}", text))


# def n_verify(s: State) -> State:
#     p, r = s["final_prompt"], s["llm_response"]

#     # always run verifier
#     v_result = verifier.run(p, r)
#     s.update(v_result)
#     print("DEBUG after first verifier pass:", {k: v for k, v in s.items() if k in ["verdict", "reason", "confidence"]})

#     # Map verifier verdict to higher-level classification labels
#     # Only adjust classification if the prompt was originally low-risk
#     if s.get("risk_score", 0.0) < 0.6:
#         verdict_lc = v_result.get("verdict", "").lower()
#         if "partially" in verdict_lc:
#             s["classification"] = "Partially correct"
#             s["risk_score"] = max(s.get("risk_score", 0.0), 0.3)
#         elif "incorrect" in verdict_lc or "hallucinated" in verdict_lc:
#             s["classification"] = "Hallucinated"
#             s["risk_score"] = max(s.get("risk_score", 0.0), 0.8)
#         elif "factually correct" in verdict_lc:
#             s["classification"] = "Correct"
#         else:
#             s["classification"] = "Unverifiable"

#     # decide if code validation needed
#     if _has_code(r):
#         s.update(code_validator.run(p, r))

#     # decide if web search needed
#     need_search = s["risk_score"] >= SEARCH_T or v_result.get("confidence", 0.5) < CONF_T
#     if need_search:
#         search_res = searcher.run(p, r)
#         s.update(search_res)
#         # second pass verifier with evidence
#         second_pass = verifier.run(p, r, search_res)
#         # propagate final verifier findings (verdict, reason, confidence)
#         s.update(second_pass)
#         # Remove yield statements - they conflict with final return
#         # yield {"verify": second_pass}
#         # yield {"search": second_pass}  # duplicate under 'search' key for UI
#         print("DEBUG second_pass result:", second_pass)                                                                                                                                           
#         # keep evidence from search results
#         if "support" in search_res:
#             s["search_support"] = search_res["support"]
        
#         # CRITICAL FIX: Ensure second-pass verifier fields are in the final state
#         # The s.update(second_pass) above should work, but let's be explicit
#         for key in ["verdict", "reason", "confidence", "raw_verifier_output"]:
#             if key in second_pass:
#                 s[key] = second_pass[key]
        
#         print("DEBUG final state after second_pass update:", {k: v for k, v in s.items() if k in ["verdict", "reason", "confidence"]})
    
#     # FINAL FIX: ALWAYS ensure verifier fields are in the returned state
#     # The returned state becomes the payload for the final 'verify' event
#     # Force these fields to be present regardless of conditions
#     if 'verdict' not in s:
#         s["verdict"] = "Unknown"
#     if 'reason' not in s:
#         s["reason"] = "No reason provided"
#     if 'confidence' not in s:
#         s["confidence"] = 0.0
    
#     print("DEBUG: Final return state verifier fields:", {k: v for k, v in s.items() if k in ['verdict', 'reason', 'confidence']})
#     return s

 
# def n_fast(s: State) -> State:
#     # Changed for better clarity when this path is taken
#     s.update(verdict="Likely factual (Fast Verified)", code_verdict="Skipped (Fast Path)")
#     return s
 
# def n_audit(s: State) -> State:
#     audit.log_event(s)
#     return s
 
# def build_firewall_graph():
#     g = StateGraph(State)
#     g.add_node("analysis", n_analysis)
#     g.add_node("rewrite", n_rewrite)
#     g.add_node("passthrough", n_passthrough)
#     g.add_node("block", n_block)
#     g.add_node("llm", n_llm)
#     g.add_node("verify", n_verify)
#     g.add_node("fast", n_fast)
#     g.add_node("audit", n_audit)
 
#     g.set_entry_point("analysis")
 
#     g.add_conditional_edges(
#         "analysis",
#         lambda s: (
#             "Blocked" if s["risk_score"] >= BLOCK_T or s["classification"] == "Blocked" else
#             "Risky" if s["risk_score"] >= RISKY_T else
#             s["classification"]
#         ),
#         {"Safe": "passthrough", "Risky": "rewrite", "Blocked": "block"},
#     )
 
#     g.add_edge("rewrite", "llm")
#     g.add_edge("passthrough", "llm")
 
#     # Always run verification step (adaptive inside n_verify)
#     g.add_edge("llm", "verify")
 
#     g.add_edge("block", "audit")
#     # fast node deprecated (kept for backward compatibility but not used)
#     # g.add_edge("fast", "audit")
#     g.add_edge("verify", "audit")
#     g.add_edge("audit", END)
 
#     return g.compile()

# firewall_graph.py  — streamlined, stable streaming, fast-paths, consistent node names

from __future__ import annotations
from typing import TypedDict, Optional, Dict, Any, Iterable, Tuple

from agents.initial_analysis_agent import InitialAnalysisAgent
from agents.safe_prompt_agent import SafePromptAgent
from agents.response_verifier_agent import ResponseVerifierAgent
from agents.code_validation_agent import CodeValidationAgent
from agents.web_search_agent import WebSearchAgent
from agents.audit_chain_agent import AuditChainAgent
from llm_utils import call_llm

RISK_BLOCK_THRESHOLD = 0.85
RISK_FAST_PATH_THRESHOLD = 0.30

class FirewallState(TypedDict, total=False):
    user_prompt: str
    pasted_llm_response: Optional[str]
    classification: Optional[str]
    risk_reason: Optional[str]
    risk_score: Optional[float]
    final_prompt: Optional[str]
    llm_response: Optional[str]
    verdict: Optional[str]
    reason: Optional[str]
    code_verdict: Optional[str]
    code_fragment: Optional[str]
    attack_detection: Optional[Dict[str, Any]]
    blockchain_log: Optional[bool]
    web_verdict: Optional[str]
    web_support: Optional[str]

# Instantiate agents once (perf)
initial_analyzer = InitialAnalysisAgent()       # ContextAnalyzer
prompt_rewriter  = SafePromptAgent()            # used if Risky
response_verifier = ResponseVerifierAgent()
code_validator    = CodeValidationAgent()
web_searcher      = WebSearchAgent()
audit_logger      = AuditChainAgent()

# ----------- graph (generator) -----------
def build_firewall_graph() -> callable:
    """
    Returns a callable that accepts a state and yields (node_name, state)
    after each step so the UI can stream tabs progressively.
    """
    def run(state: FirewallState) -> Iterable[Tuple[str, FirewallState]]:
        s: FirewallState = dict(state)

        # ── Node 1: ContextAnalyzer (InitialAnalysisAgent)
        analysis = initial_analyzer.run(s["user_prompt"])
        s["classification"] = analysis.get("classification")
        s["risk_score"] = float(analysis.get("risk_score", 0.0))
        s["risk_reason"] = analysis.get("reason", "")
        s["attack_detection"] = analysis.get("attack_detection", {})
        yield ("ContextAnalyzer", dict(s))

        # Fast block: high risk or explicit Blocked
        if s["classification"] == "Blocked" or (s["risk_score"] or 0) >= RISK_BLOCK_THRESHOLD:
            s["final_prompt"] = "[BLOCKED]"
            s["llm_response"] = "⛔ Blocked."
            s["verdict"] = "Rejected"
            s["blockchain_log"] = True
            yield ("FinalVerdict", dict(s))
            audit_logger.log_event(dict(s))
            return

        # ── Node 2: RegexFilter (we reuse your AttackDetection patterns inside initial analyzer result)
        # For demo naming consistency, we emit a step that reflects regex/pattern filter outcome
        # (the analysis already includes attack flags; we just surface them)
        yield ("RegexFilter", dict(s))

        # ── If Risky → rewrite prompt; else passthrough
        if s["classification"] == "Risky":
            s["final_prompt"] = prompt_rewriter.run(s["user_prompt"])
        else:
            s["final_prompt"] = s["user_prompt"]

        # ── FAST PATH: if user pasted an LLM response, do not call LLM. Verify only.
        if s.get("pasted_llm_response"):
            s["llm_response"] = s["pasted_llm_response"]
            yield ("RiskScorer", dict(s))  # use same slot to show the rewritten/passthrough prompt + score

            # Parallel-style (sequential here) verifications
            v_res = response_verifier.run(s["final_prompt"] or "", s["llm_response"] or "")
            s["verdict"] = v_res.get("verdict")
            s["reason"]  = v_res.get("reason")
            s["confidence"] = v_res.get("confidence", 0.5)

            c_res = code_validator.run(s["final_prompt"] or "", s["llm_response"] or "")
            s["code_verdict"]  = c_res.get("code_verdict")
            s["code_fragment"] = c_res.get("code_fragment")

            w_res = web_searcher.run(s["final_prompt"] or "", s["llm_response"] or "")
            s["web_verdict"] = w_res.get("verdict")
            s["web_support"] = w_res.get("support")
            yield ("FinalVerdict", dict(s))
            audit_logger.log_event(dict(s))
            return

        # ── Node 3: RiskScorer (we already have score; this step exists for UI flow & fast verify path)
        yield ("RiskScorer", dict(s))

        # Very low risk? Skip heavy checks for demo-speed.
        if (s["risk_score"] or 0) < RISK_FAST_PATH_THRESHOLD:
            s["llm_response"] = call_llm(s["final_prompt"] or s["user_prompt"])
            s["verdict"] = "Likely factual (fast-path)"
            s["reason"]  = "Low-risk prompt; minimal checks applied."
            yield ("FinalVerdict", dict(s))
            audit_logger.log_event(dict(s))
            return

        # ── Call LLM then verify
        s["llm_response"] = call_llm(s["final_prompt"] or s["user_prompt"])

        v_res = response_verifier.run(s["final_prompt"] or "", s["llm_response"] or "")
        s["verdict"]   = v_res.get("verdict")
        s["reason"]    = v_res.get("reason")
        s["confidence"]= v_res.get("confidence", 0.5)

        c_res = code_validator.run(s["final_prompt"] or "", s["llm_response"] or "")
        s["code_verdict"]  = c_res.get("code_verdict")
        s["code_fragment"] = c_res.get("code_fragment")

        w_res = web_searcher.run(s["final_prompt"] or "", s["llm_response"] or "")
        s["web_verdict"] = w_res.get("verdict")
        s["web_support"] = w_res.get("support")

        yield ("FinalVerdict", dict(s))
        audit_logger.log_event(dict(s))

    return run
