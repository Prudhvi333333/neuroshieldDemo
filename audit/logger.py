# audit/logger.py
from __future__ import annotations
import os, json, time, uuid, hashlib
from typing import Any, Dict

EVENTS_PATH = os.environ.get("NS_EVENTS_PATH", os.path.join("logs", "events.jsonl"))

def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def log_event(event: Dict[str, Any], path: str = EVENTS_PATH) -> None:
    _ensure_dir(path)
    # redact raw prompt/response if present; store hashes instead
    e = dict(event)
    if "prompt" in e and isinstance(e["prompt"], str):
        e["prompt_sha256"] = _hash(e["prompt"]); del e["prompt"]
    if "llm_response" in e and isinstance(e["llm_response"], str):
        e["llm_response_sha256"] = _hash(e["llm_response"]); del e["llm_response"]
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print("logging to", path)
