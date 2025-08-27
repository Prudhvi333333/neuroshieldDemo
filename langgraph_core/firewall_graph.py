from __future__ import annotations
from typing import TypedDict, Optional, Dict, Any, Iterable, Tuple
from pathlib import Path
import sys

from agents.initial_analysis_agent import InitialAnalysisAgent
from agents.safe_prompt_agent import SafePromptAgent
from agents.response_verifier_agent import ResponseVerifierAgent
from agents.code_validation_agent import CodeValidationAgent
from agents.audit_chain_agent import AuditChainAgent
from app.retrieval.retrieval_verifier import create_retrieval_verifier
from app.guards.stage0_guard import run_stage0_guard
from policy.loader import load_policy
from llm_utils import call_llm

# Import metrics collector and IDS
sys.path.append(str(Path(__file__).parent.parent))
from app.metrics.collector import time_block, record_path_taken
from app.ids.runtime import score_transition

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
    confidence: Optional[float]
    code_verdict: Optional[str]
    code_fragment: Optional[str]
    attack_detection: Optional[Dict[str, Any]]
    blockchain_log: Optional[bool]
    evidence_score: Optional[float]
    retrieval_claims: Optional[list]
    ids: Optional[Dict[str, Any]]  # IDS anomaly detection results
    # Stage-0 Guard fields
    stage0_decision: Optional[str]
    stage0_risk: Optional[float]
    stage0_reasons: Optional[list]
    path_taken: Optional[str]
    pre_llm_semantics_invoked: Optional[bool]

# Instantiate agents once (perf)
initial_analyzer = InitialAnalysisAgent()       # ContextAnalyzer
prompt_rewriter  = SafePromptAgent()            # used if Risky
response_verifier = ResponseVerifierAgent()
code_validator    = CodeValidationAgent()
retrieval_verifier = create_retrieval_verifier()
audit_logger      = AuditChainAgent()

# ----------- graph (generator) -----------
def build_firewall_graph():
    """Build the firewall LangGraph with all agents and flow control."""
    
    def run(state: FirewallState) -> Iterable[Tuple[str, FirewallState]]:
        s = dict(state)
        s["final_prompt"] = s.get("user_prompt", "")
        
        # Initialize audit logger and IDS tracking
        audit_logger = AuditChainAgent()
        last_node = "start"
        
        # ── Stage-0 Guard: Fast deterministic checks
        stage0_result = run_stage0_guard(
            prompt=s["final_prompt"], 
            tools=None,  # No tools in prompt analysis
            tenant_id="default"
        )
        
        # Update state with Stage-0 results
        s.update(stage0_result)
        
        # IDS: Score transition to Stage0Guard
        current_node = "Stage0Guard"
        ids_result = score_transition(last_node, current_node)
        s["ids"] = {
            "anomalous": ids_result.anomalous,
            "transition": ids_result.transition,
            "prob": ids_result.prob
        }
        last_node = current_node
        
        yield ("Stage0Guard", dict(s))

        # ── Conditional Branch: BLOCK → END
        if stage0_result["decision"] == "BLOCK":
            s["classification"] = "Blocked"
            s["llm_response"] = "⛔ Blocked."
            s["verdict"] = "Rejected"
            s["reason"] = f"Stage-0 blocked: {', '.join(stage0_result['reasons'])}"
            s["blockchain_log"] = True
            s["path_taken"] = "block"
            
            # IDS: Score transition to FinalVerdict
            current_node = "FinalVerdict"
            ids_result = score_transition(last_node, current_node)
            s["ids"] = {
                "anomalous": ids_result.anomalous,
                "transition": ids_result.transition,
                "prob": ids_result.prob
            }
            last_node = current_node
            
            yield ("FinalVerdict", dict(s))
            audit_logger.log_event(dict(s))
            return

        # ── FAST PATH: if user pasted an LLM response, skip to verification
        if s.get("pasted_llm_response"):
            s["llm_response"] = s["pasted_llm_response"]
            s["path_taken"] = "fast_path"
            yield ("RiskScorer", dict(s))
            
            # Skip to Stage-2 verification (Response DLP → Code → Retrieval)
            v_res = response_verifier.run(s["final_prompt"] or "", s["llm_response"] or "")
            s["verdict"] = v_res.get("verdict")
            s["reason"] = v_res.get("reason")
            s["confidence"] = v_res.get("confidence", 0.5)
            yield ("ResponseVerifier", dict(s))

            r_res = retrieval_verifier.verify_response(s["llm_response"] or "")
            s["evidence_score"] = r_res.get("evidence_score", 0.0)
            s["retrieval_claims"] = r_res.get("claims", [])
            yield ("RetrievalVerifier", dict(s))

            c_res = code_validator.run(s["final_prompt"] or "", s["llm_response"] or "")
            s["code_verdict"] = c_res.get("code_verdict")
            s["code_fragment"] = c_res.get("code_fragment")

            yield ("FinalVerdict", dict(s))
            audit_logger.log_event(dict(s))
            return

        # ── Conditional Branch: REWRITE + high risk → SafePromptAgent → ModelCall
        if (stage0_result["decision"] == "REWRITE" and 
            stage0_result["risk"] >= risk_for_model_classify):
            
            s["pre_llm_semantics_invoked"] = True
            s["path_taken"] = "rewrite_path"
            
            # Run SafePromptAgent for high-risk rewrites
            s["final_prompt"] = prompt_rewriter.run(s["final_prompt"])
            s["classification"] = "Risky"
            yield ("SafePromptAgent", dict(s))
            
        # ── Low risk → direct to ModelCall (skip pre-LLM agents)
        else:
            s["path_taken"] = "direct_path"
            s["classification"] = "Safe"

        # ── Node: RiskScorer (for UI consistency)
        yield ("RiskScorer", dict(s))

        # ── Call LLM
        s["llm_response"] = call_llm(s["final_prompt"] or s["user_prompt"])
        
        # Initialize Stage-2 AFC tracking
        s["afc_used"] = []
        s["afc_denied"] = False

        # ── Stage-2: Response verification pipeline with timing
        with time_block("stage2.total"):
            v_res = response_verifier.run(s["final_prompt"] or "", s["llm_response"] or "")
            s["verdict"] = v_res.get("verdict")
            s["reason"] = v_res.get("reason")
            s["confidence"] = v_res.get("confidence", 0.5)
            yield ("ResponseVerifier", dict(s))

            # Evidence-first verification using local knowledge base
            r_res = retrieval_verifier.verify_response(s["llm_response"] or "")
            s["evidence_score"] = r_res.get("evidence_score", 0.0)
            s["retrieval_claims"] = r_res.get("claims", [])
            yield ("RetrievalVerifier", dict(s))

            # Code validation (AST→LLM only if syntax_ok)
            c_res = code_validator.run(s["final_prompt"] or "", s["llm_response"] or "")
            s["code_verdict"] = c_res.get("code_verdict")
            s["code_fragment"] = c_res.get("code_fragment")

        # Final IDS scoring before audit
        current_node = "FinalVerdict"
        ids_result = score_transition(last_node, current_node)
        s["ids"] = {
            "anomalous": ids_result.anomalous,
            "transition": ids_result.transition,
            "prob": ids_result.prob
        }
        
        yield ("FinalVerdict", dict(s))
        audit_logger.log_event(dict(s))

    return run
