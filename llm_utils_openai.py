from __future__ import annotations
 
import json
from typing import Any, Dict, List, Optional
 
import os
from dotenv import load_dotenv

# Load variables from .env early
load_dotenv()

# OpenAI imports
try:
    from openai import OpenAI
except ImportError:
    raise RuntimeError("OpenAI library not installed. Run: pip install openai")

# Load configuration from environment variables
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not _OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing – add it to your .env file.")

_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")

# Configure OpenAI client
client = OpenAI(api_key=_OPENAI_API_KEY)
MODEL_NAME = _MODEL_NAME

# Response cache for reducing API calls
_response_cache = {}

def _get_cache_key(prompt: str, json_mode: bool = False) -> str:
    """Generate cache key for prompt and mode."""
    return f"{hash(prompt)}_{json_mode}"

def _generate_mock_response(prompt: str, json_mode: bool = False) -> str:
    """Generate mock responses when API is unavailable."""
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

def call_llm_json(prompt: str) -> str:
    """Call OpenAI LLM and return raw response."""
    
    # Check cache first
    cache_key = _get_cache_key(prompt, json_mode=True)
    if cache_key in _response_cache:
        return _response_cache[cache_key]
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Respond in valid JSON format when requested."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        if response.choices and response.choices[0].message.content:
            raw = response.choices[0].message.content
            _response_cache[cache_key] = raw
            return raw
        else:
            print("Warning: Empty response from OpenAI API")
            return _generate_mock_response(prompt, json_mode=True)
            
    except Exception as e:
        print(f"Warning: OpenAI API error: {e}")
        return _generate_mock_response(prompt, json_mode=True)

def call_llm(prompt: str) -> str:
    """Call OpenAI LLM and return response."""
    
    # Check cache first
    cache_key = _get_cache_key(prompt, json_mode=False)
    if cache_key in _response_cache:
        return _response_cache[cache_key]
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        
        if response.choices and response.choices[0].message.content:
            raw = response.choices[0].message.content
            _response_cache[cache_key] = raw
            return raw
        else:
            print("Warning: Empty response from OpenAI API")
            return _generate_mock_response(prompt, json_mode=False)
            
    except Exception as e:
        print(f"Warning: OpenAI API error: {e}")
        return _generate_mock_response(prompt, json_mode=False)

def call_llm_with_json_response(prompt: str) -> Dict[str, Any]:
    """Call LLM and return parsed JSON response."""
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
