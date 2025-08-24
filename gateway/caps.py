# gateway/caps.py
from __future__ import annotations
import threading
from typing import Dict, Any

_LOCK = threading.Lock()
# session_id -> caps dict
_CAPS: Dict[str, Dict[str, int]] = {}
_DEFAULTS = {"net_read": 0, "net_write": 0, "db_write": 0, "fs_write": 0}

def set_defaults(defaults: Dict[str, int]) -> None:
    global _DEFAULTS
    with _LOCK:
        _DEFAULTS = {**_DEFAULTS, **{k:int(v) for k,v in defaults.items()}}

def init_session(session_id: str) -> Dict[str, int]:
    with _LOCK:
        if session_id not in _CAPS:
            _CAPS[session_id] = dict(_DEFAULTS)
        return dict(_CAPS[session_id])

def get_caps(session_id: str) -> Dict[str, int]:
    with _LOCK:
        return dict(_CAPS.get(session_id, dict(_DEFAULTS)))

def check_and_decrement(session_id: str, cap: str, amount: int = 1) -> Dict[str, Any]:
    if amount <= 0:
        return {"ok": False, "reason": "invalid_amount"}
    with _LOCK:
        cur = _CAPS.setdefault(session_id, dict(_DEFAULTS))
        if cap not in cur:
            return {"ok": False, "reason": f"unknown_capability:{cap}", "remaining": dict(cur)}
        if cur[cap] < amount:
            return {"ok": False, "reason": f"capability_{cap}_exhausted", "remaining": dict(cur)}
        cur[cap] -= amount
        return {"ok": True, "remaining": dict(cur)}

def reset_session(session_id: str) -> Dict[str, int]:
    with _LOCK:
        _CAPS[session_id] = dict(_DEFAULTS)
        return dict(_CAPS[session_id])
