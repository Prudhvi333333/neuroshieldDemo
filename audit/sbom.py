# audit/sbom.py
from __future__ import annotations
import os, json, time, hashlib, uuid
from typing import Any, Dict

SBOM_PATH = os.environ.get("NS_SBOM_PATH", os.path.join("logs", "sbom.jsonl"))

def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

def _h(s: str | None) -> str | None:
    if s is None: return None
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def build_sbom(
    request_id: str,
    policy_version: str | None,
    prompt: str,
    final_prompt: str | None,
    llm_response: str | None,
    tools_used: list[str] | None,
    decision: str,
    reasons: list[str] | None,
    t1_scores: dict | None,
    qa: dict | None,
    ids: dict | None,
) -> Dict[str, Any]:
    return {
        "ts": time.time(),
        "request_id": request_id,
        "policy_version": policy_version,
        "hashes": {
            "prompt_sha256": _h(prompt),
            "final_prompt_sha256": _h(final_prompt or ""),
            "llm_response_sha256": _h(llm_response or ""),
        },
        "tools_used": tools_used or [],
        "decision": decision,
        "reasons": reasons or [],
        "signals": {
            "t1": t1_scores or {},
            "qa": qa or {},
            "ids": ids or {},
        },
        "replay_hint": {
            "endpoint": "/v1/watchman/check",
            "inputs": {"prompt": prompt, "pasted_llm_response": None},
        },
    }

def write(sbom: Dict[str, Any], path: str = SBOM_PATH) -> None:
    _ensure_dir(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(sbom, ensure_ascii=False) + "\n")
