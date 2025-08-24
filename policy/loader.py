# policy/loader.py
from __future__ import annotations
import os
import yaml
from typing import Any, Dict

_POLICY_CACHE: Dict[str, Any] = {}
_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "policy.yaml")

class PolicyError(RuntimeError):
    pass

def load_policy(path: str | None = None) -> Dict[str, Any]:
    """Load YAML policy once; reuse cached copy unless file mtime changes."""
    global _POLICY_CACHE
    path = path or _DEFAULT_PATH
    if not os.path.exists(path):
        raise PolicyError(f"Policy file not found: {path}")

    mtime = os.path.getmtime(path)
    cache_key = f"{path}:{mtime}"
    if _POLICY_CACHE.get("__key__") == cache_key:
        return _POLICY_CACHE["data"]

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # minimal validation
    if "version" not in data or "rules" not in data or "limits" not in data:
        raise PolicyError("Invalid policy: missing version/rules/limits")

    _POLICY_CACHE = {"__key__": cache_key, "data": data}
    return data
