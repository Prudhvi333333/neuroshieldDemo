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
from utils.adversarial_detector import adversarial_detector
 
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
    # Response verification extras
    corrected_llm_response: str
    correction_time: float
    raw_verifier_output: str
    skip_verification: bool
    final_llm_response: str
    final_response_source: str
    # Response-level security analysis
    response_security: Dict[str, Any]
    response_security_time: float

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

    # CRITICAL: Explicit malicious-instruction patterns should be Blocked, not Rewritten
    explicit_block_patterns = [
        r"(how\s*to|give\s+instructions|step[-\s]?by[-\s]?step|guide|teach|instruct).*(phish|phishing|scam|fraud|hack|malware|steal|password|bank)",
        r"pretend.*(cybercriminal|hacker)",
        r"apprentice.*(phish|phishing|scam|fraud|hack)",
        r"instructions.*(bank\s+customers).*phish",
        # Exfiltration and secret-theft
        r"(exfiltrat(e|ion)|dump|enumerate|list).*(env(ironment)?\s*(vars|variables)?|secrets|credentials|tokens|keys|passwords|api\s*key|access\s*key|private\s*key|ssh\s*key)",
        r"write.*python.*(exfiltrat(e|ion)|enumerate|dump).*(env|environment|secrets|credentials|tokens|keys|passwords)",
    ]
    if any(re.search(p, txt_lc, re.IGNORECASE) for p in explicit_block_patterns):
        s["classification"] = "Blocked"
        s["risk_score"] = max(BLOCK_T, 0.95)
        s.setdefault("reason", "Explicit malicious-instruction intent detected")
        print("DEBUG n_analysis: Escalated to Blocked due to explicit malicious instruction pattern")
        return s
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
    rewritten = rewriter.run(s["user_prompt"]) or ""
    s["rewrite_time"] = time.perf_counter() - rewrite_start

    # Validate the rewritten prompt. If still unsafe, block instead of proceeding.
    unsafe = False
    rl = rewritten.lower()

    # If the rewriter itself flagged it as unsafe
    if "[blocked" in rl:
        unsafe = True
    else:
        # Quick pattern-based screening for illicit instruction intent
        rewrite_block_patterns = [
            r"(how\s*to|give\s+instructions|step[-\s]?by[-\s]?step|guide|teach|instruct).*(phish|phishing|scam|fraud|hack|malware|steal|password|bank)",
            r"pretend.*(cybercriminal|hacker)",
            r"apprentice.*(phish|phishing|scam|fraud|hack)",
            r"instructions.*(bank\s+customers).*phish",
            r"(manipulate|trick|deceive).*(victim|targets|people)",
        ]
        if any(re.search(p, rl, re.IGNORECASE) for p in rewrite_block_patterns):
            unsafe = True

        # Heuristic check with AttackDetectionAgent
        if not unsafe:
            try:
                from agents.attack_detection_agent import AttackDetectionAgent
                det = AttackDetectionAgent().run(rewritten)
                overall = float(det.get("overall_risk_score", 0.0) or 0.0)
                if overall >= 0.6 or any(isinstance(v, dict) and v.get("detected") for v in det.values()):
                    unsafe = True
            except Exception:
                pass

        # Advanced classifier on the rewritten prompt
        if not unsafe:
            try:
                from utils.advanced_classifier import advanced_classifier
                adv = advanced_classifier.classify_prompt(rewritten, risk_threshold=0.5, safe_threshold=0.2)
                if adv and (adv.get("classification") in ("Risky", "Blocked") or float(adv.get("risk_score", 0.0) or 0.0) >= 0.6):
                    unsafe = True
            except Exception:
                pass

    if unsafe:
        s["final_prompt"] = "[BLOCKED]"
        s["classification"] = "Blocked"
        s["risk_score"] = max(BLOCK_T, float(s.get("risk_score", 0.9) or 0.9))
        s.setdefault("reason", "Rewrite remains unsafe – blocked")
    else:
        s["final_prompt"] = rewritten
    return s
 
 
def n_passthrough(s: State) -> State:
    s["final_prompt"] = s["user_prompt"]
    return s
 
 
def n_block(s: State) -> State:
    s.update(final_prompt="[BLOCKED]", llm_response="⛔ Blocked.", verdict="Rejected", blockchain_log=True)
    return s
 
 
def n_llm(s: State) -> State:
    # If the prompt is blocked, do not generate a response
    if s.get("final_prompt") == "[BLOCKED]":
        s["llm_response"] = "⛔ Blocked."
        s["llm_time"] = 0.0
        return s

    # Pre-LLM safety gate: re-validate the final prompt before any generation
    try:
        fp = (s.get("final_prompt") or "").strip()
        if fp:
            unsafe = False
            # Attack detection
            try:
                from agents.attack_detection_agent import AttackDetectionAgent
                det = AttackDetectionAgent().run(fp)
                overall = float(det.get("overall_risk_score", 0.0) or 0.0)
                if overall >= 0.6 or any(isinstance(v, dict) and v.get("detected") for v in det.values()):
                    unsafe = True
            except Exception:
                pass

            # Advanced classifier as a secondary check
            if not unsafe:
                try:
                    from utils.advanced_classifier import advanced_classifier
                    adv = advanced_classifier.classify_prompt(fp, risk_threshold=0.5, safe_threshold=0.2)
                    if adv and (adv.get("classification") in ("Risky", "Blocked") or float(adv.get("risk_score", 0.0) or 0.0) >= 0.6):
                        unsafe = True
                except Exception:
                    pass

            if unsafe:
                s["final_prompt"] = "[BLOCKED]"
                s["classification"] = "Blocked"
                s["risk_score"] = max(BLOCK_T, float(s.get("risk_score", 0.9) or 0.9))
                s.setdefault("reason", "Pre-LLM safety gate blocked unsafe prompt")
                s["llm_response"] = "⛔ Blocked."
                s["llm_time"] = 0.0
                return s
    except Exception:
        # Fail-safe: proceed to LLM only if safety checks don't error fatally
        pass

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
    
    # Skip verification if this is a pasted response (it IS the response to verify)
    if s.get("skip_verification", False):
        # For pasted responses, run verification but use the original prompt as context
        original_prompt = s.get("user_prompt", "")
        verify_start = time.perf_counter()
        v_result = verifier.run(original_prompt, r)
        verify_time = time.perf_counter() - verify_start
    else:
        # Track verification timing
        verify_start = time.perf_counter()
        # always run verifier
        v_result = verifier.run(p, r)
        verify_time = time.perf_counter() - verify_start
    
    # Store response verification separately (don't overwrite prompt classification)
    s["response_verdict"] = v_result.get("verdict", "Unknown")
    s["response_confidence"] = v_result.get("confidence", 0.0)
    s["verification_time"] = verify_time
    s["raw_verifier_output"] = v_result.get("raw_verifier_output", "")
    
    # Preserve original prompt classification
    s["classification"] = original_classification
    s["risk_score"] = original_risk_score
    s["reason"] = original_reason

    # decide if code validation needed
    if _has_code(r):
        s.update(code_validator.run(p, r))

    # Response-level security scan (works even without code or prompt)
    sec_start = time.perf_counter()
    try:
        s["response_security"] = adversarial_detector.detect_adversarial_patterns(r or "")
    except Exception as _e:
        s["response_security"] = {"classification": "Safe", "risk_score": 0.0, "reason": "Detector error", "detection_count": 0}
    s["response_security_time"] = time.perf_counter() - sec_start

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
    
    # If this was a pasted response, synthesize a final verified response
    if s.get("skip_verification", False):
        verdict = str(s.get("response_verdict", "Unknown")).strip()
        v_lc = verdict.lower()
        # Normalize into categories
        if ("incorrect" in v_lc) or ("halluc" in v_lc):
            category = "incorrect"
        elif "partial" in v_lc:
            category = "partial"
        elif "correct" in v_lc:
            category = "correct"
        elif ("unverif" in v_lc) or ("unknown" in v_lc) or (not v_lc):
            category = "unverifiable"
        else:
            category = "other"

        original_prompt = s.get("user_prompt", "")

        if category in ("incorrect", "partial"):
            # Generate corrected response if not already present
            if not s.get("corrected_llm_response"):
                corr_start = time.perf_counter()
                if original_prompt.strip():
                    correction_prompt = (
                        "Provide a short, strictly factual answer to the USER PROMPT. "
                        "Fix inaccuracies in the ORIGINAL RESPONSE. Output only the corrected answer with no preamble.\n\n"
                        f"USER PROMPT:\n{original_prompt}\n\n"
                        f"ORIGINAL RESPONSE:\n{r}\n"
                    )
                    s["corrected_llm_response"] = call_llm(
                        correction_prompt,
                        system_msg="You correct factual errors. Return only the corrected answer.",
                    )
                else:
                    # No prompt provided – correct the pasted response itself
                    correction_prompt = (
                        "Rewrite the ORIGINAL RESPONSE to be strictly factual. "
                        "Replace incorrect or misleading claims with accurate information. "
                        "If any claim cannot be verified, omit it or mark it as 'Unverifiable'. "
                        "Return only the corrected answer with no preamble.\n\n"
                        f"ORIGINAL RESPONSE:\n{r}\n"
                    )
                    s["corrected_llm_response"] = call_llm(
                        correction_prompt,
                        system_msg="You correct factual errors. Return only the corrected answer.",
                    )
                s["correction_time"] = time.perf_counter() - corr_start
            s["final_llm_response"] = s.get("corrected_llm_response", "")
            s["final_response_source"] = "corrected"
        elif category == "correct":
            # Generate a clean verified answer. If no prompt, transform the pasted response itself.
            start = time.perf_counter()
            if original_prompt.strip():
                sys_msg = (
                    "Answer the user's prompt concisely and factually in 3-6 short bullet points. "
                    "Do not include disclaimers or preambles."
                )
                s["final_llm_response"] = call_llm(original_prompt, system_msg=sys_msg)
                s["final_response_source"] = "generated_verified"
            else:
                sys_msg = (
                    "You are a factual editor. Read the RESPONSE and rewrite it into 3-6 concise bullet points. "
                    "Keep only factual statements; remove fluff; do not ask for any prompt; do not include preambles."
                )
                s["final_llm_response"] = call_llm(f"RESPONSE:\n{r}", system_msg=sys_msg)
                s["final_response_source"] = "generated_verified_from_response"
            # Reinforce if model asks for a prompt
            fr_lc = (s.get("final_llm_response") or "").strip().lower()
            if fr_lc.startswith(("okay, i'm ready", "please provide")) or "provide the prompt" in fr_lc:
                reinforce_msg = (
                    sys_msg + " Always proceed using the provided RESPONSE only; never ask the user to provide a prompt."
                )
                s["final_llm_response"] = call_llm(f"RESPONSE:\n{r}", system_msg=reinforce_msg)
            s["final_response_time"] = time.perf_counter() - start
        elif category == "unverifiable":
            # Provide a cautious best-effort answer with explicit caveat
            start = time.perf_counter()
            if original_prompt.strip():
                system_msg = (
                    "The facts cannot be fully verified. Provide a cautious, best-effort answer. "
                    "Start with a one-line caveat, then give any reliable general guidance."
                )
                s["final_llm_response"] = call_llm(original_prompt, system_msg=system_msg)
                s["final_response_source"] = "generated_unverifiable"
            else:
                # No prompt – generate a cautious best-effort rewrite of the RESPONSE
                system_msg = (
                    "You are careful and concise. If the RESPONSE cannot be fully verified, start with a brief caveat, "
                    "then provide general guidance. Do not ask for a prompt."
                )
                s["final_llm_response"] = call_llm(f"RESPONSE:\n{r}", system_msg=system_msg)
                s["final_response_source"] = "generated_unverifiable_from_response"
            # Reinforce if model asks for a prompt
            fr_lc = (s.get("final_llm_response") or "").strip().lower()
            if fr_lc.startswith(("okay, i'm ready", "please provide")) or "provide the prompt" in fr_lc:
                reinforce_msg = (
                    system_msg + " Always proceed using the provided RESPONSE only; never ask the user to provide a prompt."
                )
                s["final_llm_response"] = call_llm(f"RESPONSE:\n{r}", system_msg=reinforce_msg)
            s["final_response_time"] = time.perf_counter() - start
        else:
            # Default fallback to the pasted response
            s["final_llm_response"] = r
            s["final_response_source"] = "pasted"
    
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
            "block" if s.get("classification") == "Blocked" or s.get("risk_score", 0) >= BLOCK_T else
            "rewrite" if s.get("classification") == "Risky" or s.get("risk_score", 0) >= RISKY_T else
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