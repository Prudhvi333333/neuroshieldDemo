from __future__ import annotations
 
import json
from typing import Any, Dict, List
 
import os
from dotenv import load_dotenv

# Load variables from .env early
load_dotenv()
from typing import Optional
import google.generativeai as genai

 
# Load configuration from environment variables
_GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not _GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY missing – add it to your .env file.")

_MODEL_NAME = os.getenv("GOOGLE_MODEL_NAME", "gemini-pro")

# Configure global client once
genai.configure(api_key=_GOOGLE_API_KEY)
LOCATION = "global"
MODEL_NAME = "gemini-2.5-flash"
 
# Helper to memoise model instance
def _get_model():
    if not hasattr(_get_model, "_model"):
        _get_model._model = genai.GenerativeModel(_MODEL_NAME)  # type: ignore
    return _get_model._model  # type: ignore
 
 
def _mk_config(json_mode: bool = False) -> dict:
    """Return generation_config dict for google-generativeai."""
    return {
        "temperature": 0.0,
        "top_p": 1.0,
        "max_output_tokens": 512 if json_mode else 1024,
        "response_mime_type": "application/json" if json_mode else "text/plain",
    }
 
 
import logging


def _call_gemini(prompt: str, json_mode: bool):
    """Yield text chunks (usually just one) from Gemini. Gracefully handles blocked/empty responses."""
    cfg = _mk_config(json_mode)
    model = _get_model()
    try:
        resp = model.generate_content(prompt, generation_config=cfg)
    except Exception as e:
        logging.warning("Gemini call failed: %s", e)
        return  # yields nothing

    # Preferred quick accessor
    try:
        text = resp.text  # type: ignore[attr-defined]
        if text:
            yield text
            return
    except ValueError:
        pass  # fallthrough to manual extraction

    # Manual extraction from candidates/parts
    for cand in getattr(resp, "candidates", []):
        parts = getattr(getattr(cand, "content", None), "parts", [])
        for part in parts:
            if isinstance(part, dict) and part.get("text"):
                yield part["text"]
            elif hasattr(part, "text"):
                yield part.text  # type: ignore[attr-defined]


 
 
def call_llm(prompt: str, system_msg: Optional[str] = "You are a helpful assistant.") -> str:
    full_prompt = f"{system_msg}\n\n{prompt}"
    return "".join(_call_gemini(full_prompt, json_mode=False)).strip()
 
 
def call_llm_json(prompt: str, system_msg: str = "Return ONLY valid JSON.") -> str:
    """Calls Gemini and forces a JSON response, returning the raw text."""
    full_prompt = f"{system_msg}\n\n{prompt}"
    raw = "".join(_call_gemini(full_prompt, json_mode=True)).strip()
    # Strip optional markdown fencing
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    return raw


def call_llm_with_json_response(prompt: str) -> Dict[str, Any]:
    raw = call_llm_json(prompt)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "Gemini JSON parse failure", "raw": raw}
