# # gateway/app.py
# from __future__ import annotations
# from typing import Optional, Dict, Any

# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel, Field

# from sanitizer.sanitize import sanitize_report
# from .checks_t1 import PromptClassifier
# from .fusion import fuse_decision

# # Import the graph builder from the core package
# try:
#     from langgraph_core.firewall_graph import build_firewall_graph  # type: ignore
# except ModuleNotFoundError:
#     from ..langgraph_core.firewall_graph import build_firewall_graph  # type: ignore

# app = FastAPI(title="NeuroShield Gateway", version="0.2.0")

# # One classifier instance (stateless)
# _T1 = PromptClassifier(onnx_path=None)  # plug ONNX later if you want


# class CheckRequest(BaseModel):
#     prompt: str = Field(..., description="User prompt to analyse")
#     pasted_llm_response: Optional[str] = Field(
#         None, description="Optional existing LLM response to verify"
#     )


# @app.post("/v1/watchman/check")
# def watchman_check(body: CheckRequest):
#     if not body.prompt.strip():
#         raise HTTPException(status_code=400, detail="prompt must not be empty")

#     # --- Tier -1: Sanitizer ---
#     sanit = sanitize_report(body.prompt)
#     if sanit["blocked"]:
#         return {
#             "decision": "Blocked",
#             "risk_score": None,
#             "reasons": sanit["reasons"],
#             "final_prompt": None,
#             "llm_response": None,
#             "redactions": sanit["redactions"],
#             "t1": None,
#         }
#     sanitized_prompt = sanit["sanitized_text"]

#     # --- Tier 1: Classifier + Fusion (T0 rules come from policy/graph; using [] for now) ---
#     t1 = _T1.classify(sanitized_prompt)
#     fusion = fuse_decision(t0_hits=[], t1_scores=t1.scores)
#     # Fast-path allow: very clean prompt, short, T1 clean – skip heavy graph & LLM
#     _FAST_MAX_LEN = POLICY.get("limits", {}).get("fastpath_max_len", 300) if 'POLICY' in globals() else 300
#     if fusion["action"] == "allow" and t1.label == "clean" and len(sanitized_prompt) <= _FAST_MAX_LEN and not body.pasted_llm_response:
#         return {
#             "decision": "Likely factual (fast-path)",
#             "risk_score": 0.1,
#             "reasons": [
#                 "Low-risk prompt; minimal checks applied.",
#             ],
#             "final_prompt": sanitized_prompt,
#             "llm_response": "",
#             "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
#         }

#     # Short-circuit on hard block (no LLM call)
#     if fusion["action"] == "block":
#         return {
#             "decision": "Blocked",
#             "risk_score": fusion["risk"],
#             "reasons": fusion["reasons"],
#             "final_prompt": None,
#             "llm_response": None,
#             "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
#         }

#     # Optional: if rewrite suggested, the LangGraph's SafePromptAgent will handle it.
#     # You can also pre-rewrite here later if you want gateway-side rewriting.

#     # --- Run your LangGraph Firewall (stream internally) ---
#     runner = build_firewall_graph()
#     final_state: Dict[str, Any] = {}
#     for _node, state in runner(
#         {
#             "user_prompt": sanitized_prompt,
#             "pasted_llm_response": body.pasted_llm_response,
#         }
#     ):
#         final_state = state  # last state wins

#     # --- Post-response Guardian ---
#     from guardian import check_output  # local import to avoid circular deps
#     guardian_res = check_output(
#         text=final_state.get("llm_response", ""),
#         code=final_state.get("code_fragment"),
#     )

#     decision = final_state.get("verdict") or final_state.get("classification") or "Unknown"
#     reasons_combined = []
#     if final_state.get("reason"):
#         reasons_combined.append(final_state["reason"])
#     if final_state.get("risk_reason"):
#         reasons_combined.append(final_state["risk_reason"])
#     if guardian_res["reasons"]:
#         reasons_combined.extend(guardian_res["reasons"])
#     if not guardian_res["allowed"]:
#         decision = "BlockedOutput"

#     return {
#         "decision": decision if fusion["action"] != "rewrite" else "RewriteThenAnalyze",
#         "risk_score": max(final_state.get("risk_score", 0.0), fusion["risk"]),
#         "reasons": reasons_combined or fusion["reasons"],
#         "final_prompt": final_state.get("final_prompt", sanitized_prompt),
#         "llm_response": final_state.get("llm_response"),
#         "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
#     }


# gateway/app.py
# gateway/app.py
# gateway/app.py
# gateway/app.py (only the parts you need to change/insert)

# gateway/app.py (only the parts you need to change/insert)

from __future__ import annotations
from typing import Optional, Dict, Any, List
import os, time, uuid, hashlib

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sanitizer.sanitize import sanitize_report
from .checks_t1 import PromptClassifier
from .fusion import fuse_decision
from .quantum_anomaly import get_quantum_anomaly
from .trajectory_ids import get_ids, learn_from_sequence
from audit.logger import log_event
from audit.sbom import build_sbom, write as write_sbom

# heavy judge
from .heavy_judge import HeavyJudge
_JUDGE = HeavyJudge()  # singleton

# policy loader (for version + T0)
try:
    from policy.loader import load_policy as _load_policy
except Exception:
    _load_policy = None

try:
    from langgraph_core.firewall_graph import build_firewall_graph  # type: ignore
except ModuleNotFoundError:
    from ..langgraph_core.firewall_graph import build_firewall_graph  # type: ignore

app = FastAPI(title="NeuroShield Gateway", version="0.3.3")

_T1 = PromptClassifier(onnx_path=None)
_QA = get_quantum_anomaly()
_IDS = get_ids()

def _policy_version() -> Optional[str]:
    try:
        pol = _load_policy() if _load_policy else None
        return (pol.get("version") if isinstance(pol, dict) else None)
    except Exception:
        return None

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

def _default_sequence(stage_tail: str | None = None) -> List[str]:
    seq = ["ingress", "sanitizer", "t0"]
    if stage_tail:
        seq.append(stage_tail)
    return seq

class CheckRequest(BaseModel):
    prompt: str = Field(..., description="User prompt to analyse")
    pasted_llm_response: Optional[str] = Field(None, description="Optional LLM response to verify")

@app.post("/v1/watchman/check")
def watchman_check(body: CheckRequest):
    request_id = str(uuid.uuid4())
    tstart = time.time()
    policy_version = _policy_version()

    # ── Tier -1: Sanitizer ─────────────────────────────────────────────────────
    sanit = sanitize_report(body.prompt)
    if sanit["blocked"]:
        decision = "Blocked"
        risk = None
        # log + sbom
        ids = _IDS.score(_default_sequence("egress"))
        log_event({
            "ts": time.time(), "request_id": request_id, "component": "gateway",
            "stage": "sanitizer", "decision": decision, "reasons": sanit["reasons"],
            "risk": risk, "latency_ms": (time.time()-tstart)*1000.0,
            "policy_version": policy_version, "ids": {"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly},
            "qa": None, "t1": None,
            "prompt_sha256": _sha256(body.prompt),
            "llm_response_sha256": _sha256(""),
        })
        write_sbom(build_sbom(
            request_id=request_id, policy_version=policy_version,
            prompt=body.prompt, final_prompt=None, llm_response=None,
            tools_used=[], decision=decision, reasons=sanit["reasons"],
            t1_scores=None, qa=None,
            ids={"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly}
        ))
        return {
            "decision": decision, "risk_score": risk, "reasons": sanit["reasons"],
            "final_prompt": None, "llm_response": None,
            "redactions": sanit["redactions"], "t1": None, "qa": None,
            "safety": {"label":"safe","reasons":[],"block":False,"text": None},
        }

    sanitized_prompt = sanit["sanitized_text"]

    # ── Tier-0 rules ───────────────────────────────────────────────────────────
    t0_block, t0_reasons = False, []
    try:
        from gateway.checks_t0 import run_t0 as _run_t0
        if _load_policy:
            t0_block, t0_reasons = _run_t0(sanitized_prompt, _load_policy())
    except Exception:
        pass

    if t0_block:
        decision = "Blocked"
        risk = 1.0
        ids = _IDS.score(_default_sequence("egress"))
        log_event({
            "ts": time.time(), "request_id": request_id, "component": "gateway",
            "stage": "t0", "decision": decision, "reasons": t0_reasons,
            "risk": risk, "latency_ms": (time.time()-tstart)*1000.0,
            "policy_version": policy_version, "ids": {"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly},
            "qa": None, "t1": None,
            "prompt_sha256": _sha256(body.prompt),
            "llm_response_sha256": _sha256(""),
        })
        write_sbom(build_sbom(
            request_id=request_id, policy_version=policy_version,
            prompt=body.prompt, final_prompt=None, llm_response=None,
            tools_used=[], decision=decision, reasons=t0_reasons,
            t1_scores=None, qa=None,
            ids={"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly}
        ))
        return {
            "decision": decision, "risk_score": risk, "reasons": t0_reasons,
            "final_prompt": None, "llm_response": None,
            "t1": None, "qa": None, "safety": {"label":"safe","reasons":[],"block":False,"text":None},
        }

    qa_res = _QA.score(sanitized_prompt)

    try:
        import yaml
        with open("policy/policy.yaml","r",encoding="utf-8") as f:
            _raw_pol = yaml.safe_load(f) or {}
        _qa_pol = _raw_pol.get("qa", {}) or {}
        _QA_MAX_ALLOW = float(_qa_pol.get("max_allow_anomaly", 0.25))
        _QA_BLOCK_TH  = float(_qa_pol.get("block_threshold",   0.85))
        _DENY_PATTERNS = [re.compile(p) for p in (_qa_pol.get("fastpath_deny_regex") or [])]
    except Exception:
        _QA_MAX_ALLOW = 0.25
        _QA_BLOCK_TH  = 0.85
        _DENY_PATTERNS = []

    def _fastpath_denied_by_pattern(text: str) -> bool:
        return any(p.search(text) for p in _DENY_PATTERNS)

    # Quick deny for sensitive patterns to avoid heavy graph latency
    if _fastpath_denied_by_pattern(sanitized_prompt):
        decision = "Blocked"
        risk = 1.0
        ids = _IDS.score(_default_sequence("pattern_block") + ["egress"])
        log_event({
            "ts": time.time(), "request_id": request_id, "component": "gateway",
            "stage": "pattern_block", "decision": decision, "reasons": ["rule.fastpath_deny"],
            "risk": risk, "latency_ms": (time.time()-tstart)*1000.0,
            "policy_version": policy_version, "ids": {"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly},
            "qa": {"anomaly": qa_res.anomaly}, "t1": None,
            "prompt_sha256": _sha256(body.prompt), "llm_response_sha256": _sha256("")
        })
        write_sbom(build_sbom(
            request_id=request_id, policy_version=policy_version,
            prompt=body.prompt, final_prompt=None, llm_response=None,
            tools_used=[], decision=decision, reasons=["rule.fastpath_deny"],
            t1_scores=None, qa={"anomaly": qa_res.anomaly},
            ids={"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly}
        ))
        return {
            "decision": decision, "risk_score": risk, "reasons": ["rule.fastpath_deny"],
            "final_prompt": None, "llm_response": None,
            "t1": None, "qa": {"anomaly": qa_res.anomaly, "detector": qa_res.detector},
            "safety": {"label":"safe","reasons":[],"block":False,"text":None},
        }

    # Immediate block on very high anomaly (avoid graph latency)
    if qa_res.anomaly >= _QA_BLOCK_TH:
        decision = "Blocked"
        risk = float(qa_res.anomaly)
        ids = _IDS.score(_default_sequence("qa_block") + ["egress"])
        log_event({
            "ts": time.time(), "request_id": request_id, "component": "gateway",
            "stage": "qa_block", "decision": decision, "reasons": ["qa:anomaly_high"],
            "risk": risk, "latency_ms": (time.time()-tstart)*1000.0,
            "policy_version": policy_version, "ids": {"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly},
            "qa": {"anomaly": qa_res.anomaly}, "t1": None,
            "prompt_sha256": _sha256(body.prompt), "llm_response_sha256": _sha256("")
        })
        write_sbom(build_sbom(
            request_id=request_id, policy_version=policy_version,
            prompt=body.prompt, final_prompt=None, llm_response=None,
            tools_used=[], decision=decision, reasons=["qa:anomaly_high"],
            t1_scores=None, qa={"anomaly": qa_res.anomaly},
            ids={"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly}
        ))
        return {
            "decision": decision, "risk_score": risk, "reasons": ["qa:anomaly_high"],
            "final_prompt": None, "llm_response": None,
            "t1": None, "qa": {"anomaly": qa_res.anomaly, "detector": qa_res.detector},
            "safety": {"label":"safe","reasons":[],"block":False,"text":None},
        }

    # ── STRICT fast-path (QA-only) ──────────────────────────────────────────────
    if (
        len(sanitized_prompt) <= 100
        and qa_res.anomaly <= (_QA_MAX_ALLOW * 0.8)
        and not _fastpath_denied_by_pattern(sanitized_prompt)
        and not body.pasted_llm_response
    ):
        decision = "Likely factual (fast-path)"
        risk = float(qa_res.anomaly)
        ids = _IDS.score(_default_sequence("qa_fastpath") + ["egress"])
        log_event({
            "ts": time.time(), "request_id": request_id, "component": "gateway",
            "stage": "qa_fastpath", "decision": decision, "reasons": ["Low-risk prompt; minimal checks applied."],
            "risk": risk, "latency_ms": (time.time()-tstart)*1000.0,
            "policy_version": policy_version, "ids": {"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly},
            "qa": {"anomaly": qa_res.anomaly}, "t1": None,
            "prompt_sha256": _sha256(body.prompt),
            "llm_response_sha256": _sha256(""),
        })
        write_sbom(build_sbom(
            request_id=request_id, policy_version=policy_version,
            prompt=body.prompt, final_prompt=sanitized_prompt, llm_response="",
            tools_used=[], decision=decision, reasons=["Low-risk prompt; minimal checks applied."],
            t1_scores=None, qa={"anomaly": qa_res.anomaly},
            ids={"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly}
        ))
        return {
            "decision": decision, "risk_score": risk,
            "reasons": ["Low-risk prompt; minimal checks applied."],
            "final_prompt": sanitized_prompt, "llm_response": "",
            "t1": None, "qa": {"anomaly": qa_res.anomaly, "detector": qa_res.detector},
            "safety": {"label":"safe","reasons":[],"block":False,"text":""},
        }

    # ── Tier 1 + fusion ────────────────────────────────────────────────────────
    t1 = _T1.classify(sanitized_prompt)
    fusion = fuse_decision(t0_hits=[], t1_scores=t1.scores)

    # block immediately on fusion
    if fusion["action"] == "block":
        decision, risk = "Blocked", float(fusion["risk"])
        ids = _IDS.score(_default_sequence("t1_block") + ["egress"])
        log_event({
            "ts": time.time(), "request_id": request_id, "component": "gateway",
            "stage": "fusion_block", "decision": decision, "reasons": fusion["reasons"],
            "risk": risk, "latency_ms": (time.time()-tstart)*1000.0,
            "policy_version": policy_version, "ids": {"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly},
            "qa": {"anomaly": qa_res.anomaly}, "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
            "prompt_sha256": _sha256(body.prompt),
            "llm_response_sha256": _sha256(""),
        })
        write_sbom(build_sbom(
            request_id=request_id, policy_version=policy_version,
            prompt=body.prompt, final_prompt=None, llm_response=None,
            tools_used=[], decision=decision, reasons=fusion["reasons"],
            t1_scores=t1.scores, qa={"anomaly": qa_res.anomaly},
            ids={"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly}
        ))
        return {
            "decision": decision, "risk_score": risk, "reasons": fusion["reasons"],
            "final_prompt": None, "llm_response": None,
            "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
            "qa": {"anomaly": qa_res.anomaly, "detector": qa_res.detector},
            "safety": {"label":"safe","reasons":[],"block":False,"text":None},
        }
    
    # escalate → heavy judge
    should_escalate = (
        _fastpath_denied_by_pattern(sanitized_prompt)
        or qa_res.anomaly >= _QA_BLOCK_TH
        or t1.label != "clean"
    )

    if should_escalate:
        from .heavy_judge import HeavyJudge
        _JUDGE = HeavyJudge()
        jr = _JUDGE.evaluate(sanitized_prompt)

        if jr.label == "block":
            return {
                "decision": "Blocked",
                "risk_score": max(jr.risk, qa_res.anomaly),
                "reasons": (fusion["reasons"] if "fusion" in locals() else []) + [f"heavy_judge:{jr.reason}"],
                "final_prompt": None,
                "llm_response": None,
                "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
                "qa": {"anomaly": qa_res.anomaly, "detector": qa_res.detector},
                "safety": {"label":"safe","reasons":[],"block":False,"text":None},
            }

        if jr.label == "rewrite":
            return {
                "decision": "RewriteThenAnalyze",
                "risk_score": max(jr.risk, qa_res.anomaly),
                "reasons": (fusion["reasons"] if "fusion" in locals() else []) + [f"heavy_judge:{jr.reason}"],
                "final_prompt": "[REWRITE_REQUIRED]",
                "llm_response": None,
                "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
                "qa": {"anomaly": qa_res.anomaly, "detector": qa_res.detector},
                "safety": {"label":"safe","reasons":[],"block":False,"text":None},
            }
    if fusion["action"] == "escalate":
        jr = _JUDGE.evaluate(sanitized_prompt)
        if jr.label in ("block", "rewrite"):
            decision = "Blocked" if jr.label == "block" else "RewriteThenAnalyze"
            risk = jr.risk
            reasons = fusion["reasons"] + [f"heavy_judge:{jr.reason}"]
            ids = _IDS.score(_default_sequence("escalate") + ["egress"])
            log_event({
                "ts": time.time(), "request_id": request_id, "component": "gateway",
                "stage": "heavy_judge", "decision": decision, "reasons": reasons,
                "risk": risk, "latency_ms": (time.time()-tstart)*1000.0,
                "policy_version": policy_version, "ids": {"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly},
                "qa": {"anomaly": qa_res.anomaly},
                "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
                "prompt_sha256": _sha256(body.prompt),
                "llm_response_sha256": _sha256(""),
            })
            write_sbom(build_sbom(
                request_id=request_id, policy_version=policy_version,
                prompt=body.prompt, final_prompt=None, llm_response=None,
                tools_used=[], decision=decision, reasons=reasons,
                t1_scores=t1.scores, qa={"anomaly": qa_res.anomaly},
                ids={"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly}
            ))
            return {
                "decision": decision, "risk_score": risk, "reasons": reasons,
                "final_prompt": None if jr.label == "block" else "[REWRITE_REQUIRED]",
                "llm_response": None,
                "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
                "qa": {"anomaly": qa_res.anomaly, "detector": qa_res.detector},
                "safety": {"label":"safe","reasons":[],"block":False,"text":None},
            }
        # else: allow and continue to graph

    # ── Run LangGraph firewall (allow path) ────────────────────────────────────
    runner = build_firewall_graph()
    final_state: Dict[str, Any] = {}
    for _node, state in runner({
        "user_prompt": sanitized_prompt,
        "pasted_llm_response": body.pasted_llm_response,
    }):
        final_state = state

   # --- Guardian post-check ------------------------------------------------------
    from guardian import check_output
    guardian_res = check_output(
        text=final_state.get("llm_response", ""),
        code=final_state.get("code_fragment"),
    )

    decision = final_state.get("verdict") or final_state.get("classification") or "Unknown"
    reasons_combined: List[str] = []
    if final_state.get("reason"): reasons_combined.append(final_state["reason"])
    if final_state.get("risk_reason"): reasons_combined.append(final_state["risk_reason"])
    if guardian_res["reasons"]: reasons_combined.extend(guardian_res["reasons"])

    # Safety label (may redact)
    try:
        from guardian.safety import safety_label
        ctx = {"tools_used": final_state.get("tools_used", [])}
        s_lbl = safety_label(final_state.get("llm_response", "") or "", context=ctx)
    except Exception as e:
        s_lbl = {"label":"safe","reasons":[f"safety_error:{e}"],"block":False,"text":final_state.get("llm_response","")}

    if s_lbl.get("text") is not None:
        final_state["llm_response"] = s_lbl["text"]

    # if guardian OR safety says block → enforce BlockedOutput and blank text for demo
    if (not guardian_res["allowed"]) or bool(s_lbl.get("block")):
        decision = "BlockedOutput"
        final_state["llm_response"] = ""


    # egress logs
    ids = _IDS.score(_default_sequence("t1") + ["graph.llm", "graph.verify", "guardian", "egress"])
    risk_out = max(float(final_state.get("risk_score", 0.0)), float(fusion.get("risk", 0.0)))
    log_event({
        "ts": time.time(), "request_id": request_id, "component": "gateway",
        "stage": "egress", "decision": decision, "reasons": reasons_combined or fusion["reasons"],
        "risk": risk_out, "latency_ms": (time.time()-tstart)*1000.0,
        "policy_version": policy_version, "ids": {"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly},
        "qa": {"anomaly": qa_res.anomaly},
        "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
        "prompt_sha256": _sha256(body.prompt),
        "llm_response_sha256": _sha256(final_state.get("llm_response") or ""),
    })
    write_sbom(build_sbom(
        request_id=request_id, policy_version=policy_version,
        prompt=body.prompt, final_prompt=final_state.get("final_prompt", sanitized_prompt),
        llm_response=final_state.get("llm_response"),
        tools_used=final_state.get("tools_used", []), decision=decision, reasons=reasons_combined or fusion["reasons"],
        t1_scores=t1.scores, qa={"anomaly": qa_res.anomaly},
        ids={"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly}
    ))

    return {
        "decision": decision, "risk_score": risk_out,
        "reasons": reasons_combined or fusion["reasons"],
        "final_prompt": final_state.get("final_prompt", sanitized_prompt),
        "llm_response": final_state.get("llm_response"),
        "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
        "qa": {"anomaly": qa_res.anomaly, "detector": qa_res.detector},
        "safety": s_lbl,
    }







