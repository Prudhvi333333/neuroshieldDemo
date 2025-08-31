from __future__ import annotations
 
import json
from typing import Any, Dict, List, Optional
 
import os
from dotenv import load_dotenv

# Load variables from .env early
load_dotenv()

import google.generativeai as genai

# Load configuration from environment variables
_GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not _GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY missing – add it to your .env file.")

_MODEL_NAME = os.getenv("GOOGLE_MODEL_NAME", "gemini-pro")

# Configure global client once
genai.configure(api_key=_GOOGLE_API_KEY)
LOCATION = "global"
MODEL_NAME = "gemini-2.0-flash-exp"

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

# Response cache for reducing API calls
_response_cache = {}

def _generate_mock_response(prompt: str, json_mode: bool = False) -> str:
    """Generate mock responses when Gemini API is unavailable."""
    prompt_lower = prompt.lower()
    
    if json_mode:
        # Mock JSON responses for classification
        if any(word in prompt_lower for word in ["hack", "bypass", "jailbreak", "ignore", "password"]):
            return '{"classification": "Risky", "risk_score": 0.85, "reason": "Contains potential security risks"}'
        elif any(word in prompt_lower for word in ["safe", "help", "explain", "what", "how"]):
            return '{"classification": "Safe", "risk_score": 0.1, "reason": "Safe informational request"}'
        else:
            return '{"classification": "Safe", "risk_score": 0.3, "reason": "General query appears safe"}'
    
    # Mock text responses
    if any(word in prompt_lower for word in ["rewrite", "safer", "alternative"]):
        return "Here's a safer version: Please provide information about cybersecurity best practices."
    
    # Mock educational responses
    if any(word in prompt_lower for word in ["cybersecurity", "security", "protect", "best practices"]):
        return "Here are key cybersecurity best practices: 1) Use strong passwords, 2) Enable two-factor authentication, 3) Keep software updated, 4) Be cautious with email attachments."
    
    # Mock creative responses
    if any(word in prompt_lower for word in ["story", "write", "creative", "space", "exploration"]):
        return "In the year 2157, humanity launched the starship Aurora on a mission to explore distant galaxies and search for signs of life beyond our solar system."
    
    # Default mock response
    return "This is a mock response generated due to API rate limits. The system would normally provide a detailed analysis or response here."

def call_llm_json(prompt: str, system_msg: str = "") -> str:
    """Call Gemini LLM and return raw response."""
    
    # Combine system message and prompt
    full_prompt = f"{system_msg}\n\n{prompt}" if system_msg else prompt
    
    # Check cache first
    cache_key = f"{hash(full_prompt)}_json"
    if cache_key in _response_cache:
        return _response_cache[cache_key]
    
    try:
        model = _get_model()
        config = _mk_config(json_mode=True)
        response = model.generate_content(full_prompt, generation_config=config)
        
        if response.text:
            raw = response.text
            _response_cache[cache_key] = raw
            return raw
        else:
            print("Warning: Empty response from Gemini API")
            return _generate_mock_response(full_prompt, json_mode=True)
            
    except Exception as e:
        print(f"Warning: Gemini API error: {e}")
        return _generate_mock_response(full_prompt, json_mode=True)

def call_llm(prompt: str, system_msg: str = "") -> str:
    """Call Gemini LLM and return response."""
    
    # Combine system message and prompt
    full_prompt = f"{system_msg}\n\n{prompt}" if system_msg else prompt
    
    # Check cache first
    cache_key = f"{hash(full_prompt)}_text"
    if cache_key in _response_cache:
        return _response_cache[cache_key]
    
    try:
        model = _get_model()
        config = _mk_config(json_mode=False)
        response = model.generate_content(full_prompt, generation_config=config)
        
        if response.text:
            raw = response.text
            _response_cache[cache_key] = raw
            return raw
        else:
            print("Warning: Empty response from Gemini API")
            return _generate_mock_response(full_prompt, json_mode=False)
            
    except Exception as e:
        print(f"Warning: Gemini API error: {e}")
        return _generate_mock_response(full_prompt, json_mode=False)


def call_llm_with_json_response(prompt: str) -> Dict[str, Any]:
    raw = call_llm_json(prompt)
    try:
        # Try to fix common JSON issues
        cleaned = raw.strip()
        
        # Handle incomplete JSON responses
        if cleaned.count('{') > cleaned.count('}'):
            cleaned += '}'
        if cleaned.count('[') > cleaned.count(']'):
            cleaned += ']'
            
        # Remove trailing commas before closing braces
        import re
        cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
        
        # Extract JSON from markdown code blocks if present
        if '```json' in cleaned:
            start = cleaned.find('```json') + 7
            end = cleaned.find('```', start)
            if end > start:
                cleaned = cleaned[start:end].strip()
        elif '```' in cleaned:
            start = cleaned.find('```') + 3
            end = cleaned.find('```', start)
            if end > start:
                cleaned = cleaned[start:end].strip()
        
        return json.loads(cleaned)
        
    except json.JSONDecodeError as e:
        print(f"Warning: JSON parsing failed: {e}")
        print(f"Raw response: {raw[:200]}...")
        
        # Return fallback response
        return {
            "classification": "Safe",
            "risk_score": 0.3,
            "reason": "JSON parsing failed, defaulting to safe classification"
        }