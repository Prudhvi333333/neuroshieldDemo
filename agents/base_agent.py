from __future__ import annotations
 
import functools
import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
 
from llm_utils import call_llm
 
_JSON_RE = re.compile(r"\{.*?}", re.DOTALL)
 
 
def safe_json(text: str) -> Optional[Dict[str, Any]]:
    m = _JSON_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
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
 
    @abstractmethod
    def run(self, *args, **kwargs):
        ...