from __future__ import annotations
 
import functools
import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
 
from llm_utils import call_llm, call_llm_json
 
# Greedy match to capture the largest JSON block (handles nested braces better)
_JSON_RE = re.compile(r"\{.*}\s*$", re.DOTALL)
 
 
def safe_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse the **largest** JSON object from the given text.
    This is robust against nested braces common in Gemini outputs.
    """
    # First try direct parse
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data = {k.lower(): v for k, v in data.items()}
        return data
    except Exception:
        pass

    # Fallback: regex extract
    m = _JSON_RE.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        if isinstance(data, dict):
            data = {k.lower(): v for k, v in data.items()}
        return data
    except json.JSONDecodeError:
        return None
 
 
class BaseAgent(ABC):
    _CACHE = functools.lru_cache(maxsize=256)
 
    def __init__(self, name: str):
        self.name = name
 
    @_CACHE
    def _cached_llm(self, prompt: str, system_msg: str) -> str:
        return call_llm(prompt, system_msg)
 
    def reason(self, prompt: str, system_msg: Optional[str] = None) -> str:
        return self._cached_llm(
            prompt,
            (system_msg or f"You are {self.name}. Think step by step.").strip(),
        )
 
    def call_llm_with_json_response(self, prompt: str, system_msg: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Call Gemini requesting JSON and return a parsed dictionary, or None on failure."""
        response_text = call_llm_json(prompt, system_msg or "Return ONLY valid JSON.")
        return safe_json(response_text)

    def reason_json(self, prompt: str, system_msg: Optional[str] = None) -> Dict[str, Any]:
        """LLM reasoning expecting STRICT JSON. Falls back to best-effort parse."""
        data = self.call_llm_with_json_response(prompt, system_msg)
        if data is not None:
            return data
        # best-effort fallback using generic call then extract JSON
        raw = self._cached_llm(prompt, (system_msg or "Return ONLY JSON.").strip())
        return safe_json(raw) or {}

    @abstractmethod
    def run(self, *args, **kwargs):
        ...