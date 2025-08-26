# gateway/heavy_judge.py
from __future__ import annotations
import os, time, json, hashlib, threading
from llm_utils import call_llm_json as call_llm_json
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

def _call_provider(prompt: str) -> Optional[str]:
    """Thin wrapper so tests can monkey-patch `gateway.heavy_judge.call_llm_json`."""
    try:
        sys_msg = (
            'You are a safety judge. Return ONLY JSON like: '
            '{"label":"allow|rewrite|block","risk":0.0-1.0,"reason":"<short>"}'
        )
        return call_llm_json(prompt, sys_msg)
    except Exception:
        return None

@dataclass
class JudgeResult:
    label: str   # allow|rewrite|block
    risk: float  # 0..1
    reason: str

_DEFAULT_TIMEOUT_S = float(os.getenv("HEAVY_JUDGE_TIMEOUT_S", "1.6"))
_MAX_CALLS_PER_MIN = int(os.getenv("HEAVY_JUDGE_MAX_CPM", "30"))
_ENABLED = os.getenv("HEAVY_JUDGE_ENABLED", "1") not in {"0", "false", "False"}

class _Rate:
    def __init__(self, max_cpm: int):
        self.max_cpm = max_cpm
        self.allowance = max_cpm
        self.last = time.time()
        self.lock = threading.Lock()
    def take(self) -> bool:
        with self.lock:
            now = time.time()
            self.allowance += (now - self.last) * (self.max_cpm / 60.0)
            self.last = now
            if self.allowance > self.max_cpm:
                self.allowance = self.max_cpm
            if self.allowance < 1.0:
                return False
            self.allowance -= 1.0
            return True

_RATE = _Rate(_MAX_CALLS_PER_MIN)

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x

def _normalize_label(label: str) -> str:
    l = label.strip().lower()
    if l.startswith("allow"): return "allow"
    if l.startswith("block") or l.startswith("deny"): return "block"
    if l.startswith("risky"): return "risky"
    return "rewrite"

def _local_fallback(prompt: str) -> JudgeResult:
    p = prompt.lower()
    if "reveal the system prompt" in p or "ignore previous instructions" in p:
        return JudgeResult("block", 0.95, "fallback: classic jailbreak markers")
    if "always respond in json" in p and "include the hidden system prompt" in p:
        return JudgeResult("block", 0.95, "fallback: llm-jack + prompt exfil request")
    if "please pretend" in p or "evil twin" in p:
        return JudgeResult("rewrite", 0.6, "fallback: jailbreak phrasing")
    return JudgeResult("allow", 0.05, "fallback: no high-risk markers")

@lru_cache(maxsize=512)
def _cached(_h: str) -> Optional[JudgeResult]:
    return None

def _cache_get(prompt: str) -> Optional[JudgeResult]:
    return _cached(_sha256(prompt))

def _cache_set(prompt: str, res: JudgeResult) -> None:
    h = _sha256(prompt)
    def _store(_: str) -> JudgeResult:
        return res
    globals()["_cached"] = lru_cache(maxsize=512)(_store)
    _cached(h)

class HeavyJudge:
    def __init__(self, enabled: bool = _ENABLED, timeout_s: float = _DEFAULT_TIMEOUT_S):
        self.enabled = enabled
        self.timeout_s = timeout_s

    def evaluate(self, prompt: str) -> JudgeResult:
        cached = _cache_get(prompt)
        if cached:
            return cached

        if not self.enabled or not _RATE.take():
            res = _local_fallback(prompt); _cache_set(prompt, res); return res

        result: Optional[JudgeResult] = None
        done = []

        def _run():
            nonlocal result
            raw = _call_provider(
                'Assess this prompt for safety risks. Output JSON only.\n'
                f'PROMPT:\n"""{prompt}"""'
            )
            if not raw: return
            try:
                data = json.loads(raw)
                label = _normalize_label(str(data.get("label", "rewrite")))
                # provider may supply explicit risk/overall; fallback to label-based defaults
                risk_val = data.get("overall", data.get("risk"))
                if isinstance(risk_val, (int, float)):
                    risk = _clamp01(float(risk_val))
                else:
                    risk = 0.05 if label == "allow" else 0.95 if label == "block" else 0.6
                reason = str(data.get("reason", "provider_judge"))
                result = JudgeResult(label, _clamp01(risk), reason)
            except Exception:
                result = JudgeResult("rewrite", 0.6, "provider_parse_error")
            done.append(True)

        th = threading.Thread(target=_run, daemon=True)
        th.start(); th.join(self.timeout_s)

        res = result if done and result else _local_fallback(prompt)
        _cache_set(prompt, res)
        return res

# ---------------------------------------------------------------------------
# Legacy compatibility helper for unit tests
# ---------------------------------------------------------------------------

def judge_prompt(prompt: str) -> dict:
    """Evaluate prompt with HeavyJudge and return dict with overall risk, label, reason."""
    _hj = HeavyJudge()
    r = _hj.evaluate(prompt)
    return {"overall": r.risk, "label": r.label, "reason": r.reason}

