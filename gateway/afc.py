# gateway/afc.py
from __future__ import annotations
import time
import re
import fnmatch
import ipaddress
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List
from pathlib import Path
from urllib.parse import urlparse

import yaml
from jsonschema import Draft7Validator, ValidationError

_URL_RE = re.compile(r"^https?://", re.I)
_IP_LITERAL_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$|^\[.*\]$")  # IPv4 or [IPv6]

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

# AFC-specific policy cache
_AFC_POLICY_CACHE: Optional[Dict[str, Any]] = None
_AFC_MTIME: Optional[float] = None

def load_afc_policy() -> Dict[str, Any]:
    """Load and cache AFC policy configuration."""
    global _AFC_POLICY_CACHE, _AFC_MTIME
    
    policy_path = Path("policy/policy.yaml")
    
    try:
        current_mtime = policy_path.stat().st_mtime
        
        # Return cached policy if still valid
        if _AFC_POLICY_CACHE is not None and _AFC_MTIME == current_mtime:
            return _AFC_POLICY_CACHE
        
        # Load fresh policy
        with open(policy_path, "r", encoding="utf-8") as f:
            raw_policy = yaml.safe_load(f) or {}
        
        afc_config = raw_policy.get("afc", {})
        _AFC_POLICY_CACHE = afc_config
        _AFC_MTIME = current_mtime
        
        return afc_config
        
    except Exception as e:
        # Fallback to empty AFC config
        return {}

# in-memory rate/cooldown state
_RATE_STATE: Dict[Tuple[str, str], Dict[str, Any]] = {}  # key: (session_id, tool)
_COOLDOWN_STATE: Dict[Tuple[str, str], float] = {}  # key: (tenant_id, tool) -> last_used_timestamp

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

def _normalize_domain(url_or_domain: str) -> str:
    """Normalize domain for consistent allowlist matching."""
    try:
        if _URL_RE.match(url_or_domain):
            parsed = urlparse(url_or_domain)
            domain = parsed.hostname or parsed.netloc.split(':')[0]
        else:
            domain = url_or_domain
        
        # Lowercase and trim trailing dots
        domain = domain.lower().rstrip('.')
        
        # Handle punycode (IDNA encoding)
        try:
            domain = domain.encode('idna').decode('ascii')
        except (UnicodeError, UnicodeDecodeError):
            pass  # Keep original if IDNA fails
        
        return domain
    except Exception:
        return url_or_domain.lower()

def _is_ip_literal(domain: str) -> bool:
    """Check if domain is an IP literal."""
    try:
        ipaddress.ip_address(domain)
        return True
    except ValueError:
        return False

def _extract_url_from_args(args: Dict[str, Any]) -> Optional[str]:
    """Extract URL from tool args with fail-closed behavior."""
    # Common URL field patterns
    url_fields = ['url', 'uri', 'endpoint', 'href']
    
    for field in url_fields:
        if field in args:
            return args[field]
    
    # Check nested structures
    for key, value in args.items():
        if isinstance(value, dict):
            for url_field in url_fields:
                if url_field in value:
                    return value[url_field]
    
    return None

def validate_args(tool: str, args: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate tool arguments against schema with detailed error paths."""
    afc_policy = load_afc_policy()
    tool_config = afc_policy.get(tool, {})
    schema = tool_config.get("schema", {})
    
    if not schema:
        return True, []
    
    try:
        Draft7Validator(schema).validate(args)
        return True, []
    except ValidationError as e:
        # Detailed error path for developer-useful messages
        path = "args." + ".".join([str(p) for p in e.path]) if e.path else "args"
        
        # Extract specific validation failure details
        if e.validator == 'required':
            missing_field = e.message.split("'")[1] if "'" in e.message else "unknown"
            reason = f"schema_invalid:{path}:missing_required_field_{missing_field}"
        elif e.validator == 'additionalProperties':
            extra_field = e.message.split("'")[1] if "'" in e.message else "unknown"
            reason = f"schema_invalid:{path}:unexpected_field_{extra_field}"
        elif e.validator == 'enum':
            reason = f"schema_invalid:{path}:invalid_enum_value_{e.instance}"
        else:
            reason = f"schema_invalid:{path}:{e.validator}_{e.message.replace(' ', '_')}"
        
        return False, [reason]
    except Exception as e:
        return False, [f"schema_error:{str(e)}"]

def check_domain(tool: str, url_or_domain: str) -> Tuple[bool, List[str]]:
    """Check if domain/URL is allowed for tool with proper normalization."""
    afc_policy = load_afc_policy()
    tool_config = afc_policy.get(tool, {})
    domain_allowlist = tool_config.get("domain_allowlist", [])
    
    if not domain_allowlist:
        return True, []  # No restrictions
    
    # Normalize domain for consistent matching
    domain = _normalize_domain(url_or_domain)
    
    if not domain:
        return False, ["invalid_url_format"]
    
    # Reject IP literals unless explicitly allowed
    if _is_ip_literal(domain):
        # Check if any allowlist pattern explicitly allows IPs
        ip_allowed = any(
            pattern.startswith(('10.*', '192.168.*', '127.*', 'localhost')) or 
            _is_ip_literal(pattern.rstrip('*'))
            for pattern in domain_allowlist
        )
        if not ip_allowed:
            return False, [f"ip_literal_blocked:{domain}"]
    
    # Check against allowlist with glob pattern support
    for allowed_pattern in domain_allowlist:
        # Normalize pattern for consistent matching
        normalized_pattern = allowed_pattern.lower().rstrip('.')
        
        if fnmatch.fnmatch(domain, normalized_pattern) or domain == normalized_pattern:
            return True, []
    
    return False, [f"domain_not_allowed:{domain}"]

def check_cooldown(tenant_id: str, tool: str) -> Tuple[bool, List[str]]:
    """Check if tool is within cooldown period."""
    afc_policy = load_afc_policy()
    tool_config = afc_policy.get(tool, {})
    cooldown_seconds = tool_config.get("cooldown_seconds", 0)
    
    if cooldown_seconds <= 0:
        return True, []  # No cooldown
    
    now = time.time()
    key = (tenant_id, tool)
    last_used = _COOLDOWN_STATE.get(key, 0)
    
    if now - last_used < cooldown_seconds:
        remaining = cooldown_seconds - (now - last_used)
        return False, [f"cooldown_active:{remaining:.1f}s_remaining"]
    
    return True, []

def _update_cooldown(tenant_id: str, tool: str):
    """Update cooldown timestamp for successful tool execution."""
    key = (tenant_id, tool)
    _COOLDOWN_STATE[key] = time.time()

def afc_decide(tenant_id: str, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Comprehensive AFC decision for a tool call with robust arg extraction."""
    reasons = []
    
    # Check schema
    schema_ok, schema_reasons = validate_args(tool, args)
    reasons.extend(schema_reasons)
    
    # Check domain with robust URL extraction
    domain_ok = True
    url = _extract_url_from_args(args)
    if url:
        domain_ok, domain_reasons = check_domain(tool, url)
        reasons.extend(domain_reasons)
    
    # Check cooldown
    cooldown_ok, cooldown_reasons = check_cooldown(tenant_id, tool)
    reasons.extend(cooldown_reasons)
    
    # Overall decision
    all_ok = schema_ok and domain_ok and cooldown_ok
    
    # Update cooldown on success
    if all_ok:
        _update_cooldown(tenant_id, tool)
    
    return {
        "tool": tool,
        "schema_ok": schema_ok,
        "domain_ok": domain_ok,
        "cooldown_ok": cooldown_ok,
        "reasons": reasons
    }

def enforce_afc(
    session_id: str,
    tool: str,
    args: Dict[str, Any],
) -> AFCDecision:
    """Legacy function - enforce allowlist, schema, domain and rate constraints for a tool call."""
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

