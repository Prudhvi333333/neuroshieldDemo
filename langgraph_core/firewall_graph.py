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
            s["verdict"] = "Likely factual (fast-path)"
            s["reason"]  = "Low-risk prompt; no external LLM call."
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
