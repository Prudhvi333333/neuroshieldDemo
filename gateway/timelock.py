# gateway/timelock.py
from __future__ import annotations
import time
import uuid
import threading
from typing import Dict, Any, Optional, Tuple

_LOCK = threading.Lock()
_QUEUE: Dict[str, Dict[str, Any]] = {}  # id -> record

def _now() -> float:
    return time.time()

def create(tool: str, args: Dict[str, Any], ttl_seconds: int) -> Dict[str, Any]:
    tid = uuid.uuid4().hex[:12]
    rec = {
        "id": tid,
        "tool": tool,
        "args": args,
        "created_at": _now(),
        "ttl": int(ttl_seconds),
        "status": "pending",
        "expires_at": _now() + int(ttl_seconds),
    }
    with _LOCK:
        _QUEUE[tid] = rec
    return dict(rec)

def cancel(tid: str) -> Dict[str, Any]:
    with _LOCK:
        rec = _QUEUE.get(tid)
        if not rec:
            return {"ok": False, "reason": "not_found"}
        if rec["status"] != "pending":
            return {"ok": False, "reason": f"not_pending:{rec['status']}"}
        rec["status"] = "cancelled"
        return {"ok": True, "record": dict(rec)}

def poll(tid: str) -> Dict[str, Any]:
    with _LOCK:
        rec = _QUEUE.get(tid)
        if not rec:
            return {"ok": False, "reason": "not_found"}
        # auto-expire to 'ready' if time passed
        if rec["status"] == "pending" and _now() >= rec["expires_at"]:
            rec["status"] = "ready"
        return {"ok": True, "record": dict(rec)}

def purge_expired(max_age_seconds: int = 3600) -> int:
    """Optional house-keeping."""
    now = _now()
    with _LOCK:
        to_del = [k for k,v in _QUEUE.items() if now - v["created_at"] > max_age_seconds]
        for k in to_del:
            del _QUEUE[k]
        return len(to_del)
