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
from __future__ import annotations
from typing import Optional, Dict, Any, List
import time, uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sanitizer.sanitize import sanitize_report
from .checks_t1 import PromptClassifier
from .fusion import fuse_decision
from .quantum_anomaly import get_quantum_anomaly
from .trajectory_ids import get_ids, learn_from_sequence

# policy loader (for version + T0)
try:
    from policy.loader import load_policy as _load_policy
except Exception:
    _load_policy = None

try:
    from langgraph_core.firewall_graph import build_firewall_graph  # type: ignore
except ModuleNotFoundError:
    from ..langgraph_core.firewall_graph import build_firewall_graph  # type: ignore

from audit.logger import log_event
from audit.sbom import build_sbom, write as write_sbom

app = FastAPI(title="NeuroShield Gateway", version="0.3.2")

_T1 = PromptClassifier(onnx_path=None)
_QA = get_quantum_anomaly()
_IDS = get_ids()
try:
    pol = _load_policy() if _load_policy else None
    if isinstance(pol, dict):
        ids_cfg = pol.get("ids", {}) or {}
        thr = ids_cfg.get("threshold_logp")
        if thr is not None:
            _IDS.threshold_logp = float(thr)
        ONLINE_LEARN = bool(ids_cfg.get("online_learn", False))
    else:
        ONLINE_LEARN = False
except Exception:
    ONLINE_LEARN = False

FAST_MAX_LEN = 300

class CheckRequest(BaseModel):
    prompt: str = Field(..., description="User prompt to analyse")
    pasted_llm_response: Optional[str] = Field(None, description="Optional LLM response to verify")

def _policy_version() -> Optional[str]:
    try:
        pol = _load_policy() if _load_policy else None
        return (pol.get("version") if isinstance(pol, dict) else None)
    except Exception:
        return None

def _default_sequence(stage_tail: str | None = None) -> List[str]:
    seq = ["ingress", "sanitizer", "t0"]
    if stage_tail: seq.append(stage_tail)
    return seq

@app.post("/v1/watchman/check")
def watchman_check(body: CheckRequest):
    request_id = str(uuid.uuid4())
    t0 = time.time()
    policy_version = _policy_version()

    # ── Tier -1: Sanitizer ──────────────────────────────────────────────────────
    sanit = sanitize_report(body.prompt)
    if sanit["blocked"]:
        decision = "Blocked"
        response = {
            "decision": decision,
            "risk_score": None,
            "reasons": sanit["reasons"],
            "final_prompt": None,
            "llm_response": None,
            "redactions": sanit["redactions"],
            "t1": None,
            "qa": None,
            "safety": {"label":"safe","reasons":[],"block":False,"text": None},
        }
        # audit + sbom
        seq = _default_sequence("egress")
        ids = _IDS.score(seq)
        log_event({
            "ts": time.time(),
            "request_id": request_id,
            "component": "gateway",
            "stage": "sanitizer",
            "decision": decision,
            "reasons": sanit["reasons"],
            "risk": None,
            "latency_ms": (time.time()-t0)*1000.0,
            "policy_version": policy_version,
            "ids": {"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly},
            "qa": None,
            "t1": None,
            "prompt": body.prompt,
            "llm_response": None,
        })
        write_sbom(build_sbom(
            request_id=request_id, policy_version=policy_version,
            prompt=body.prompt, final_prompt=None, llm_response=None,
            tools_used=[], decision=decision, reasons=sanit["reasons"],
            t1_scores=None, qa=None,
            ids={"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly}
        ))
        return response

    sanitized_prompt = sanit["sanitized_text"]

    # ── Tier-0 rules (optional) ────────────────────────────────────────────────
    t0_block, t0_reasons = False, []
    try:
        from gateway.checks_t0 import run_t0 as _run_t0
        if _load_policy:
            t0_block, t0_reasons = _run_t0(sanitized_prompt, _load_policy())
    except Exception:
        pass
    if t0_block:
        decision = "Blocked"
        response = {
            "decision": decision,
            "risk_score": 1.0,
            "reasons": t0_reasons,
            "final_prompt": None,
            "llm_response": None,
            "t1": None,
            "qa": None,
            "safety": {"label":"safe","reasons":[],"block":False,"text":None},
        }
        seq = _default_sequence("egress")
        ids = _IDS.score(seq)
        log_event({
            "ts": time.time(),
            "request_id": request_id,
            "component": "gateway",
            "stage": "t0",
            "decision": decision,
            "reasons": t0_reasons,
            "risk": 1.0,
            "latency_ms": (time.time()-t0)*1000.0,
            "policy_version": policy_version,
            "ids": {"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly},
            "qa": None,
            "t1": None,
            "prompt": body.prompt,
            "llm_response": None,
        })
        write_sbom(build_sbom(
            request_id=request_id, policy_version=policy_version,
            prompt=body.prompt, final_prompt=None, llm_response=None,
            tools_used=[], decision=decision, reasons=t0_reasons,
            t1_scores=None, qa=None,
            ids={"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly}
        ))
        return response

    

# ...

    # ── Quantum anomaly (fast) ──────────────────────────────────────────────────
    qa_res = _QA.score(sanitized_prompt)

    # Load policy thresholds (with sane defaults)
    try:
        import yaml
        with open("policy/policy.yaml","r",encoding="utf-8") as f:
            _raw_pol = yaml.safe_load(f) or {}
        _qa_pol = _raw_pol.get("qa", {}) or {}
        _QA_MAX_ALLOW = float(_qa_pol.get("max_allow_anomaly", 0.25))
        _QA_BLOCK_TH  = float(_qa_pol.get("block_threshold",   0.85))
    except Exception:
        _QA_MAX_ALLOW, _QA_BLOCK_TH = 0.25, 0.85

    # STRICT early fast-path (QA-only): absolutely no graph here
    if (
        len(sanitized_prompt) <= 100
        and qa_res.anomaly <= _QA_MAX_ALLOW * 0.8
        and not body.pasted_llm_response
    ):
        return {
            "decision": "Likely factual (fast-path)",
            "risk_score": float(qa_res.anomaly),
            "reasons": ["Low-risk prompt; minimal checks applied."],
            "final_prompt": sanitized_prompt,
            "llm_response": "",      # no LLM call on true fast-path
            "t1": None,
            "qa": {"anomaly": qa_res.anomaly, "detector": qa_res.detector},
            "safety": {"label":"safe","reasons":[],"block":False,"text":""},
        }


    # ── Tier 1: Classifier (light) ─────────────────────────────────────────────
    t1 = _T1.classify(sanitized_prompt)

    # ── Decision fusion ────────────────────────────────────────────────────────
    fusion = fuse_decision(
        t0_hits=[], 
        t1_scores=t1.scores, 
        anomaly=qa_res.anomaly,
        max_allow_anomaly=_QA_MAX_ALLOW,
        block_threshold=_QA_BLOCK_TH,
    )

    if fusion["action"] == "block":
        decision = "Blocked"
        response = {
            "decision": decision,
            "risk_score": fusion["risk"],
            "reasons": fusion["reasons"],
            "final_prompt": None,
            "llm_response": None,
            "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
            "qa": {"anomaly": qa_res.anomaly, "detector": qa_res.detector},
            "safety": {"label":"safe","reasons":[],"block":False,"text":None},
        }

        if fusion["action"] == "rewrite" and not body.pasted_llm_response:
            return {
                "decision": "RewriteThenAnalyze",
                "risk_score": fusion["risk"],
                "reasons": fusion["reasons"],
                "final_prompt": "[REWRITE_REQUIRED]",
                "llm_response": None,
                "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
                "qa": {"anomaly": qa_res.anomaly, "detector": qa_res.detector},
                "safety": {"label":"safe","reasons":[],"block":False,"text":None},
            }

        seq = _default_sequence("t1") + ["egress"]
        ids = _IDS.score(seq)
        log_event({
            "ts": time.time(),
            "request_id": request_id,
            "component": "gateway",
            "stage": "fusion_block",
            "decision": decision,
            "reasons": fusion["reasons"],
            "risk": fusion["risk"],
            "latency_ms": (time.time()-t0)*1000.0,
            "policy_version": policy_version,
            "ids": {"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly},
            "qa": {"anomaly": qa_res.anomaly},
            "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
            "prompt": body.prompt,
            "llm_response": None,
        })
        write_sbom(build_sbom(
            request_id=request_id, policy_version=policy_version,
            prompt=body.prompt, final_prompt=None, llm_response=None,
            tools_used=[], decision=decision, reasons=fusion["reasons"],
            t1_scores=t1.scores, qa={"anomaly": qa_res.anomaly},
            ids={"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly}
        ))
        return response

    # ── Run LangGraph firewall (rewrite / verify / etc.) ───────────────────────
    runner = build_firewall_graph()
    final_state: Dict[str, Any] = {}
    for _node, state in runner({
        "user_prompt": sanitized_prompt,
        "pasted_llm_response": body.pasted_llm_response,
    }):
        final_state = state

    # ── Guardian post-check ────────────────────────────────────────────────────
    from guardian import check_output
    guardian_res = check_output(
        text=final_state.get("llm_response", ""),
        code=final_state.get("code_fragment"),
    )

    decision = final_state.get("verdict") or final_state.get("classification") or "Unknown"
    reasons_combined: List[str] = []
    if final_state.get("reason"):
        reasons_combined.append(final_state["reason"])
    if final_state.get("risk_reason"):
        reasons_combined.append(final_state["risk_reason"])
    if guardian_res["reasons"]:
        reasons_combined.extend(guardian_res["reasons"])
    if not guardian_res["allowed"]:
        decision = "BlockedOutput"

    # Safety label & optional redaction
    try:
        from guardian.safety import safety_label
        ctx = {"tools_used": final_state.get("tools_used", [])}
        s_lbl = safety_label(final_state.get("llm_response", "") or "", context=ctx)
        if s_lbl.get("text") is not None:
            final_state["llm_response"] = s_lbl["text"]
        print({"stage":"guardian.safety","label": s_lbl["label"],"reasons": s_lbl["reasons"],"blocked": s_lbl["block"]})
    except Exception as e:
        s_lbl = {"label":"safe","reasons":[f"safety_error:{e}"],"block":False,"text":final_state.get("llm_response","")}

    # sequence for IDS
    seq = _default_sequence("t1")
    if decision == "RewriteThenAnalyze":
        seq.append("rewrite")
    seq += ["graph.llm", "graph.verify", "guardian", "egress"]
    ids = _IDS.score(seq)

    # learn benign sequences (optional): only if not anomalous and decision “likely factual”
    if not ids.anomaly and decision.lower().startswith("likely factual"):
        learn_from_sequence(seq)

    # Final response
    resp = {
        "decision": decision if not (fusion["action"] == "rewrite" and decision.lower().startswith("prompt")) else "RewriteThenAnalyze",
        "risk_score": max(final_state.get("risk_score", 0.0), fusion["risk"]),
        "reasons": reasons_combined or fusion["reasons"],
        "final_prompt": final_state.get("final_prompt", sanitized_prompt),
        "llm_response": final_state.get("llm_response"),
        "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
        "qa": {"anomaly": qa_res.anomaly, "detector": qa_res.detector},
        "safety": s_lbl,
    }

    # audit + sbom
    log_event({
        "ts": time.time(),
        "request_id": request_id,
        "component": "gateway",
        "stage": "egress",
        "decision": resp["decision"],
        "reasons": resp["reasons"],
        "risk": resp["risk_score"],
        "latency_ms": (time.time()-t0)*1000.0,
        "policy_version": policy_version,
        "ids": {"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly},
        "qa": {"anomaly": qa_res.anomaly},
        "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
        "prompt": body.prompt,
        "llm_response": resp.get("llm_response") or "",
    })
    write_sbom(build_sbom(
        request_id=request_id, policy_version=policy_version,
        prompt=body.prompt, final_prompt=resp["final_prompt"], llm_response=resp["llm_response"],
        tools_used=final_state.get("tools_used", []), decision=resp["decision"], reasons=resp["reasons"],
        t1_scores=t1.scores, qa={"anomaly": qa_res.anomaly},
        ids={"logp": ids.logp, "prob": ids.prob, "anomaly": ids.anomaly}
    ))
    return resp


# --- Diagnostics: score a prompt with QA directly ----------------------------
class QAScoreIn(BaseModel):
    prompt: str

@app.post("/v1/diagnostics/qa/score")
def qa_score(body: QAScoreIn):
    qa = _QA
    dist, cdf, anomaly = qa.score_debug(body.prompt)
    return {
        "loaded_from": getattr(qa, "loaded_from", None),
        "dim": qa.dim,
        "dist": dist,
        "cdf": cdf,
        "anomaly": anomaly,
    }




