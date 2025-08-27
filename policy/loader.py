# policy/loader.py
from __future__ import annotations
import os
import yaml
import hashlib
from datetime import datetime
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

    _POLICY_CACHE = {"__key__": cache_key, "data": data, "path": path, "mtime": mtime}
    return data


def get_policy_version(path: str | None = None) -> str:
    """Get policy version string for display purposes."""
    path = path or _DEFAULT_PATH
    if not os.path.exists(path):
        return "unknown"
    
    try:
        # Load policy to ensure cache is populated
        policy = load_policy(path)
        
        # Get file modification time
        mtime = os.path.getmtime(path)
        dt = datetime.fromtimestamp(mtime)
        
        # Create version string: policy.version + timestamp + hash
        policy_version = policy.get("version", "1.0")
        timestamp = dt.strftime("%Y-%m-%d.%H%M")
        
        # Generate short hash of policy content
        with open(path, "rb") as f:
            content_hash = hashlib.md5(f.read()).hexdigest()[:8]
        
        return f"{policy_version}-{timestamp}-{content_hash}"
    except Exception:
        return "error"


def reload_policy(path: str | None = None) -> bool:
    """Force reload policy from disk, clearing cache."""
    global _POLICY_CACHE
    path = path or _DEFAULT_PATH
    
    try:
        # Clear cache to force reload
        _POLICY_CACHE.clear()
        load_policy(path)
        return True
    except Exception:
        return False
