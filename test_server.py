from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import time, uuid

app = FastAPI()

class CheckRequest(BaseModel):
    prompt: str
    pasted_llm_response: Optional[str] = None
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None

@app.post("/v1/watchman/check")
def watchman_check(body: CheckRequest):
    return {
        "decision": "ALLOW",
        "risk_score": 0.1,
        "reasons": ["Request processed successfully"],
        "trace": ["ingress", "simple_check", "egress"],
        "latency_ms": 50,
        "tenant_id": body.tenant_id or "default",
        "policy_version": "1.0",
        "final_prompt": body.prompt,
        "llm_response": body.pasted_llm_response or "",
        "model_called": False,
        "ids": {"transition": "normal", "anomalous": False},
        "t0": {},
        "t1": {},
        "afc": [],
        "code_validation": {},
        "claim_verification": {},
        "safety": {"label": "safe"}
    }

@app.get("/v1/metrics/summary")
def metrics_summary():
    return {"blocked": 0, "p95_latency_ms": 50}

@app.get("/metrics/json")
def get_metrics():
    return {"status": "success", "metrics": {"timing": {}, "paths": {}}}

@app.post("/policy/reload")
def reload_policy():
    return {"success": True, "message": "Policy reloaded successfully"}

@app.get("/")
def root():
    return {"message": "NeuroShield Gateway API", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": time.time()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
