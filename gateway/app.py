"""Gateway FastAPI service exposing /v1/watchman/check.

This lightweight wrapper calls the internal firewall graph and returns the
final decision and details in JSON form. It is **offline-friendly** and does
not stream results back to the client – the streaming happens only
internally to obtain the last state.
"""
from __future__ import annotations

from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sanitizer.sanitize import sanitize_report

# Import the graph builder from the core package
try:
    from langgraph_core.firewall_graph import build_firewall_graph  # type: ignore
except ModuleNotFoundError:
    # Fallback to relative import when running inside repository layout
    from langgraph_core.firewall_graph import build_firewall_graph  # type: ignore

app = FastAPI(title="NeuroShield Gateway", version="0.1.0")


class CheckRequest(BaseModel):
    prompt: str = Field(..., description="User prompt to analyse")
    pasted_llm_response: Optional[str] = Field(
        None, description="Optional existing LLM response to verify"
    )


@app.post("/v1/watchman/check")
def watchman_check(body: CheckRequest):
    """Run the firewall graph and return the final decision JSON."""
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")

    # --- Sanitize input first ---
    sanit = sanitize_report(body.prompt)
    if sanit["blocked"]:
        return {
            "decision": "Blocked",
            "risk_score": None,
            "reasons": sanit["reasons"],
            "final_prompt": None,
            "llm_response": None,
            "redactions": sanit["redactions"],
        }

    sanitized_prompt = sanit["sanitized_text"]

    runner = build_firewall_graph()
    final_state: Dict[str, Any] = {}

    # Execute graph – yields (node_name, state) tuples
    for yielded in runner({
        "user_prompt": sanitized_prompt,
        "pasted_llm_response": body.pasted_llm_response,
    }):
        if isinstance(yielded, tuple) and len(yielded) == 2:
            _node, state = yielded
        else:
            state = yielded
        final_state = state

    # --- Guardian post-check on LLM output ---
    from guardian import check_output  # local import to avoid circular deps
    guardian_res = check_output(
        text=final_state.get("llm_response", ""),
        code=final_state.get("code_fragment"),
    )

    decision = final_state.get("verdict") or final_state.get("classification")
    reasons_combined = []
    if final_state.get("reason"):
        reasons_combined.append(final_state["reason"])
    if final_state.get("risk_reason"):
        reasons_combined.append(final_state["risk_reason"])
    if guardian_res["reasons"]:
        reasons_combined.extend(guardian_res["reasons"])
    if not guardian_res["allowed"]:
        decision = "BlockedOutput"

    response_json = {
        "decision": decision,
        "risk_score": final_state.get("risk_score"),
        "reasons": reasons_combined,
        "final_prompt": final_state.get("final_prompt"),
        "llm_response": final_state.get("llm_response"),
    }
    return response_json
