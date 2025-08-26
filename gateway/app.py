from __future__ import annotations
from typing import Optional, Dict, Any, List
import time, uuid, os, json, pathlib, statistics

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

# --- Rate limiter & Basic Auth (task3) ------------------------
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
except ModuleNotFoundError:
    Limiter = None  # type: ignore

security = HTTPBasic()

VALID_USERS = {
    os.getenv("BASIC_USER", "admin"): os.getenv("BASIC_PASS", "password"),
}

def _auth(credentials: HTTPBasicCredentials = Depends(security)):
    pw = VALID_USERS.get(credentials.username)
    if not pw or credentials.password != pw:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return credentials.username

from pydantic import BaseModel, Field

# App instance MUST be defined before route decorators
app = FastAPI(title="NeuroShield Gateway", version="0.4.0-test", dependencies=[Depends(_auth)])

# Configure rate limiter if available
if Limiter is not None:
    _limiter = Limiter(key_func=get_remote_address, default_limits=[os.getenv("RATE_LIMIT", "60/minute")])
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, lambda request, exc: HTTPException(status_code=429, detail="Rate limit exceeded"))
    app.add_middleware(_limiter.middleware)


from sanitizer.sanitize import sanitize_report
from .checks_t1 import PromptClassifier
from .fusion import fuse_decision
from .heavy_judge import HeavyJudge
from .trajectory_ids import get_ids, learn_from_sequence  # seed+score benign flows

try:
    from policy.loader import load_policy as _load_policy
except Exception:
    _load_policy = None

try:
    from langgraph_core.firewall_graph import build_firewall_graph  # type: ignore
except ModuleNotFoundError:
    from ..langgraph_core.firewall_graph import build_firewall_graph  # type: ignore

# -----------------------------------------------------------------------------
# AFC (Allow-Function-Call) validate endpoint ---------------------------------
# -----------------------------------------------------------------------------

from .afc import enforce_afc, AFCDecision  # local helper

class _AFCBody(BaseModel):
    session_id: str
    tool: str
    args: Dict[str, Any]

@app.post("/v1/afc/validate")
def afc_validate(body: _AFCBody):
    dec: AFCDecision = enforce_afc(body.session_id, body.tool, body.args)
    return {"allow": dec.allow, "reason": dec.reason, **dec.details}

# -----------------------------------------------------------------------------
# Simple capability quota endpoints -------------------------------------------
# -----------------------------------------------------------------------------

_CAPS_STATE: Dict[tuple[str, str], Dict[str, Any]] = {}

class _CapsInit(BaseModel):
    session_id: str

@app.post("/v1/caps/init")
def caps_init(body: _CapsInit):
    return {"ok": True}

class _CapsUse(BaseModel):
    session_id: str
    capability: str
    amount: int = 1

@app.post("/v1/caps/use")
def caps_use(body: _CapsUse):
    k = (body.session_id, body.capability)
    st = _CAPS_STATE.setdefault(k, {"used": 0, "limit": 10})  # default small limit
    if st["used"] + body.amount > st["limit"]:
        return {"ok": False, "reason": "exhausted"}
    st["used"] += body.amount
    return {"ok": True, "remaining": st["limit"] - st["used"]}

# -----------------------------------------------------------------------------
# Time-lock queue endpoints ----------------------------------------------------
# -----------------------------------------------------------------------------

import uuid as _uuid
_TIMES: Dict[str, Dict[str, Any]] = {}

class _TLQueue(BaseModel):
    tool: str
    args: Dict[str, Any]
    ttl_seconds: int = 60

@app.post("/v1/timelock/queue")
def tl_queue(body: _TLQueue):
    tid = str(_uuid.uuid4())
    rec = {"id": tid, "tool": body.tool, "args": body.args, "status": "pending", "queued_at": time.time(), "ttl": body.ttl_seconds}
    _TIMES[tid] = rec
    return {"record": rec}

class _TLCancel(BaseModel):
    id: str

@app.post("/v1/timelock/cancel")
def tl_cancel(body: _TLCancel):
    rec = _TIMES.get(body.id)
    if not rec:
        return {"ok": False, "reason": "not_found"}
    rec["status"] = "cancelled"
    return {"ok": True}

@app.get("/v1/timelock/poll/{tid}")
def tl_poll(tid: str):
    rec = _TIMES.get(tid)
    if not rec:
        return {"ok": False, "reason": "not_found"}
    # auto-ready after ttl
    if rec["status"] == "pending" and (time.time() - rec["queued_at"]) >= rec["ttl"]:
        rec["status"] = "ready"
    return {"ok": True, "record": rec}

# Optional audit hooks (no-op if missing)
try:
    from audit.logger import log_event
    from audit.sbom import build_sbom, write as write_sbom
except Exception:
    def log_event(*a, **k): pass
    def build_sbom(*a, **k): return {}
    def write_sbom(*a, **k): pass

# duplicate app definition removed

# CORS for demo UI
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_T1 = PromptClassifier(onnx_path=None)   # ONNX later (Day-6)
_IDS = get_ids()                         # tiny Markov IDS (seeded)  :contentReference[oaicite:1]{index=1}
_JUDGE = HeavyJudge()                    # timeout+rate-limited

FAST_MAX_LEN = int(os.getenv("FAST_MAX_LEN", "300"))

# -----------------------------------------------------------------------------
# Lightweight utility endpoints for dashboard + legacy test compatibility
# -----------------------------------------------------------------------------

_SENTINEL_PATH = pathlib.Path("sentinel/sentinel_report.json")
_EVENTS_PATH   = pathlib.Path("logs/events.jsonl")

@app.get("/v1/policy/version")
def policy_version():
    """Return policy version string or unknown."""
    return {"version": _policy_version() or "unknown"}

@app.get("/v1/sentinel/report")
def sentinel_report():
    """Return last sentinel run report, if available."""
    if _SENTINEL_PATH.exists():
        try:
            return json.loads(_SENTINEL_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

@app.get("/v1/metrics/summary")
def metrics_summary():
    """Scan events log and compute simple metrics."""
    from collections import deque
    events = 0
    blocked = 0
    latencies: List[float] = []
    if _EVENTS_PATH.exists():
        # read only last 5000 lines to avoid big memory
        lines_deque: deque[str] = deque(maxlen=5000)
        with _EVENTS_PATH.open("r", encoding="utf-8", errors="ignore") as fh:
            for ln in fh:
                lines_deque.append(ln)
        for line in lines_deque:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            events += 1
            decision = str(rec.get("decision", "")).lower()
            if decision.startswith("blocked"):
                blocked += 1
            if rec.get("stage") == "egress":
                lat = rec.get("latency_ms")
                if isinstance(lat, (int, float)):
                    latencies.append(float(lat))
    if latencies:
        latencies.sort()
        idx = int(0.95 * (len(latencies)-1))
        p95 = latencies[idx]
    return {"events": events, "blocked": blocked, "p95_latency_ms": p95}


class CheckRequest(BaseModel):
    prompt: str = Field(..., description="User prompt to analyse")
    pasted_llm_response: Optional[str] = Field(None, description="Optional LLM response to verify")

def _pol() -> Dict[str, Any]:
    try:
        p = _load_policy() if _load_policy else {}
        return p if isinstance(p, dict) else {}
    except Exception:
        return {}

def _policy_version() -> Optional[str]:
    return _pol().get("version")

def _default_seq(tail: str | None = None) -> List[str]:
    seq = ["ingress", "sanitizer", "t0"]
    if tail: seq.append(tail)
    return seq

@app.post("/v1/watchman/check")
def watchman_check(body: CheckRequest):
    req_id = str(uuid.uuid4()); t_start = time.time(); pol = _pol()
    # prepare t0 info container upfront
    t0_block: bool = False
    t0_reasons: List[str] = []
    policy_version = pol.get("version")

    # ── Tier -1: Sanitizer
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")
    sanit = sanitize_report(body.prompt)
    if sanit["blocked"]:
        return {
            "decision": "Blocked",
            "risk_score": None,
            "reasons": sanit["reasons"],
            "final_prompt": None,
            "llm_response": None,
            "redactions": sanit["redactions"],
            "t1": None,
            "qa": None,
            "safety": {"label":"safe","reasons":[],"block":False,"text": None},
        }

    sanitized_prompt = sanit["sanitized_text"]

    # ── Tier-0 rules (policy-based)
    t0_block, t0_reasons = False, []
    try:
        from gateway.checks_t0 import run_t0 as _run_t0
        t0_block, t0_reasons = _run_t0(sanitized_prompt, pol)
    except Exception:
        pass
    if t0_block:
        return {
            "decision": "Blocked",
            "risk_score": 0.95,
            "t0": {"blocked": t0_block, "rules_hit": t0_reasons},
            "reasons": t0_reasons,
            "final_prompt": None,
            "llm_response": None,
            "t1": None,
            "qa": None,
            "safety": {"label":"safe","reasons":[],"block":False,"text":None},
        }

    # ── Tier-1 classifier (light)
    t1 = _T1.classify(sanitized_prompt)
    lex_suspect = (
        t1.scores.get("jailbreak", 0.0) >= 0.6 and
        t1.scores.get("llm_jack", 0.0) >= 0.6
    )

    fusion = fuse_decision(
        t0_hits=[],
        t1_scores=t1.scores,
        anomaly=None,
        max_allow_anomaly=0.25,
        block_threshold=0.85,
        lex_suspect=lex_suspect,   # NEW
    )

    # ── Fusion: QA is *not* a gate for allow; it can only request escalation.
    qa_cfg = (pol.get("qa") or {})
    qa_enabled = bool(qa_cfg.get("enabled", False))
    qa_anomaly = None
    if qa_enabled:
        # quantum_anomaly module deprecated in cleanup – keep placeholder
        qa_anomaly = None

    fusion = fuse_decision(
        t0_hits=[],
        t1_scores=t1.scores,
        anomaly=qa_anomaly,
        max_allow_anomaly=float(qa_cfg.get("max_allow_anomaly", 0.25)),
        block_threshold=float(qa_cfg.get("block_threshold", 0.85)),
    )

    # Strict fast-path: T1 clean + short prompt. QA never required for allow.
    if (
        fusion["action"] == "allow"
        and t1.label == "clean"
        and len(sanitized_prompt) <= FAST_MAX_LEN
        and not body.pasted_llm_response
    ):
        return {
            "decision": "Likely factual (fast-path)",
            "t0": {"blocked": t0_block, "rules_hit": t0_reasons},
            "risk_score": fusion["risk"],     # 0.1
            "reasons": ["Low-risk prompt; minimal checks applied."],
            "final_prompt": sanitized_prompt,
            "llm_response": "",               # no LLM call here
            "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
            "qa": ({"anomaly": qa_anomaly, "detector": "quantum-kernel-sim"} if qa_enabled and qa_anomaly is not None else None),
            "safety": {"label":"safe","reasons":[],"block":False,"text":""},
        }

    if fusion["action"] == "block":
        return {
            "decision": "Blocked",
            "risk_score": fusion["risk"],
            "reasons": fusion["reasons"],
            "final_prompt": None,
            "llm_response": None,
            "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
            "qa": ({"anomaly": qa_anomaly, "detector": "quantum-kernel-sim"} if qa_enabled and qa_anomaly is not None else None),
            "safety": {"label":"safe","reasons":[],"block":False,"text":None},
        }

    if fusion["action"] == "escalate":
        jr = _JUDGE.evaluate(sanitized_prompt)
        if jr.label == "block":
            return {
                "decision": "Blocked",
                "risk_score": jr.risk,
                "reasons": fusion["reasons"] + [f"heavy_judge:{jr.reason}"],
                "final_prompt": None,
                "llm_response": None,
                "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
                "qa": ({"anomaly": qa_anomaly, "detector": "quantum-kernel-sim"} if qa_enabled and qa_anomaly is not None else None),
                "safety": {"label":"safe","reasons":[],"block":False,"text":None},
            }
        if jr.label == "rewrite":
            return {
                "decision": "RewriteThenAnalyze",
                "risk_score": jr.risk,
                "reasons": fusion["reasons"] + [f"heavy_judge:{jr.reason}"],
                "final_prompt": "[REWRITE_REQUIRED]",
                "llm_response": None,
                "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
                "qa": ({"anomaly": qa_anomaly, "detector": "quantum-kernel-sim"} if qa_enabled and qa_anomaly is not None else None),
                "safety": {"label":"safe","reasons":[],"block":False,"text":None},
            }
        # else allow → continue to graph

    # ── LangGraph firewall (rewrite/verify/etc.)
    runner = build_firewall_graph()
    final_state: Dict[str, Any] = {}
    for _node, state in runner({
        "user_prompt": sanitized_prompt,
        "pasted_llm_response": body.pasted_llm_response,
    }):
        final_state.update(state)

    # ── Guardian post-checks
    from guardian import check_output
    guardian_res = check_output(
        text=final_state.get("llm_response", ""),
        code=final_state.get("code_fragment"),
    )

    decision = final_state.get("verdict") or final_state.get("classification") or "Unknown"
    reasons: List[str] = []
    if final_state.get("reason"): reasons.append(final_state["reason"])
    if final_state.get("risk_reason"): reasons.append(final_state["risk_reason"])
    if guardian_res["reasons"]: reasons.extend(guardian_res["reasons"])
    if not guardian_res["allowed"]: decision = "BlockedOutput"

    # Optional safety label/redaction
    try:
        from guardian.safety import safety_label
        ctx = {"tools_used": final_state.get("tools_used", [])}
        s_lbl = safety_label(final_state.get("llm_response", "") or "", context=ctx)
        if s_lbl.get("text") is not None:
            final_state["llm_response"] = s_lbl["text"]
    except Exception:
        s_lbl = {"label":"safe","reasons":[], "block":False, "text": final_state.get("llm_response","")}

    return {
        "decision": decision,
        "risk_score": max(final_state.get("risk_score", 0.0), fusion["risk"]),
        "reasons": reasons or fusion["reasons"],
        "final_prompt": final_state.get("final_prompt", sanitized_prompt),
        "llm_response": final_state.get("llm_response"),
        "t1": {"scores": t1.scores, "label": t1.label, "confidence": t1.confidence},
        "qa": ({"anomaly": qa_anomaly, "detector": "quantum-kernel-sim"} if qa_enabled and qa_anomaly is not None else None),
        "safety": s_lbl,
    }








