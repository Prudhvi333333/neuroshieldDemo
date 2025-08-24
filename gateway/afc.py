# gateway/afc.py
from __future__ import annotations
import time
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import yaml
from jsonschema import Draft7Validator, ValidationError

_URL_RE = re.compile(r"^https?://", re.I)

@dataclass
class AFCDecision:
    allow: bool
    reason: str
    details: Dict[str, Any]

class Policy:
    def __init__(self, raw: Dict[str, Any]):
        self.version = raw.get("version", "unknown")
        self.tools = {}
        for t in raw.get("tools", []):
            name = t["name"]
            self.tools[name] = {
                "allow": bool(t.get("allow", False)),
                "domains_allow": t.get("domains_allow", []),
                "rate": t.get("rate", {}),
                "args_schema": t.get("args_schema", {}),
            }

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        return self.tools.get(name)

class PolicyLoader:
    _policy_cache: Optional[Policy] = None
    _mtime: Optional[float] = None
    _path: str = "policy/policy.yaml"

    @classmethod
    def load(cls) -> Policy:
        try:
            with open(cls._path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            return Policy(raw)
        except Exception:
            # fallback: empty policy
            return Policy({"version": "fallback", "tools": []})

# in-memory rate/cooldown state
_RATE_STATE: Dict[Tuple[str, str], Dict[str, Any]] = {}  # key: (session_id, tool)

def _domain_ok(url: str, allowlist: list[str]) -> bool:
    if not _URL_RE.match(url):
        return False
    try:
        host = url.split("//", 1)[1].split("/", 1)[0].lower()
    except Exception:
        return False
    return any(host == d or host.endswith(f".{d}") for d in allowlist)

def _validate_schema(args: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
    try:
        Draft7Validator(schema).validate(args)
        return None
    except ValidationError as e:
        path = ".".join([str(p) for p in e.path]) if e.path else ""
        return f"args_invalid:{path or 'root'}:{e.message}"

def _rate_check(session_id: str, tool: str, rate_cfg: Dict[str, Any]) -> Optional[str]:
    if not rate_cfg:
        return None
    now = time.time()
    max_calls = int(rate_cfg.get("max_calls", 0))
    per_seconds = int(rate_cfg.get("per_seconds", 60))
    cooldown = int(rate_cfg.get("cooldown_seconds", 0))

    if max_calls <= 0:
        return "rate_limited:disabled"

    k = (session_id, tool)
    st = _RATE_STATE.setdefault(k, {"window_start": now, "count": 0, "last_call": 0.0})

    # reset window
    if now - st["window_start"] > per_seconds:
        st["window_start"] = now
        st["count"] = 0

    # cooldown check
    if cooldown > 0 and (now - st["last_call"]) < cooldown:
        return "cooldown_active"

    if st["count"] >= max_calls:
        return "rate_limited:max_calls"

    # book the call
    st["count"] += 1
    st["last_call"] = now
    return None

def enforce_afc(
    session_id: str,
    tool: str,
    args: Dict[str, Any],
) -> AFCDecision:
    """
    Enforce allowlist, schema, domain and rate constraints for a tool call.
    session_id: caller/session key (can be app/user id)
    tool: tool name (e.g., 'web.get')
    args: JSON args for the tool
    """
    policy = PolicyLoader.load()
    spec = policy.get_tool(tool)
    if not spec:
        return AFCDecision(False, "tool_not_allowed:unknown_tool", {"policy_version": policy.version})

    if not spec.get("allow", False):
        return AFCDecision(False, "tool_not_allowed", {"policy_version": policy.version})

    # schema validation
    schema = spec.get("args_schema", {})
    if schema:
        err = _validate_schema(args, schema)
        if err:
            return AFCDecision(False, err, {"policy_version": policy.version})

    # domain allowlist for URL-style tools
    if spec.get("domains_allow"):
        # naive convention: look for 'url' in args
        url = args.get("url", "")
        if not _domain_ok(url, spec["domains_allow"]):
            return AFCDecision(False, "domain_not_allowed", {"policy_version": policy.version, "url": url})

    # rate / cooldown
    err = _rate_check(session_id, tool, spec.get("rate", {}))
    if err:
        return AFCDecision(False, err, {"policy_version": policy.version})

    return AFCDecision(True, "allow", {"policy_version": policy.version})

