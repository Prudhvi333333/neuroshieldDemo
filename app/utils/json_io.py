"""
Strict JSON I/O utilities for NeuroShield agents.
Provides robust LLM JSON parsing with validation and retry logic.
"""
from __future__ import annotations

import json
import re
import logging
from typing import Any, Dict, Optional
from jsonschema import validate, ValidationError

from llm_utils import call_llm_json as _call_llm_json


class JsonParseError(Exception):
    """Raised when JSON parsing fails after all retries."""
    pass


def _extract_json_block(text: str) -> str:
    """Extract the first JSON block from text, handling markdown fencing."""
    text = text.strip()
    
    # Remove markdown fencing if present
    if text.startswith("```json") and text.endswith("```"):
        lines = text.split("\n")
        return "\n".join(lines[1:-1])
    elif text.startswith("```") and text.endswith("```"):
        lines = text.split("\n")
        return "\n".join(lines[1:-1])
    
    # Find JSON block using regex (greedy match for nested objects)
    json_pattern = re.compile(r'\{.*\}', re.DOTALL)
    match = json_pattern.search(text)
    if match:
        return match.group(0)
    
    return text


def call_llm_json(prompt: str, schema: Dict[str, Any], retries: int = 2) -> Dict[str, Any]:
    """
    Call LLM with strict JSON validation and retry logic.
    
    Args:
        prompt: The prompt to send to the LLM
        schema: JSON schema for validation
        retries: Number of retry attempts (default: 2)
        
    Returns:
        Validated JSON dictionary
        
    Raises:
        JsonParseError: If parsing fails after all retries
    """
    logger = logging.getLogger(__name__)
    
    for attempt in range(retries + 1):
        try:
            # Call the LLM
            raw_text = _call_llm_json(prompt, "Return ONLY valid JSON that matches the required schema.")
            
            # Log raw response for audit
            logger.info(f"[JSON_IO] Attempt {attempt + 1} - Raw LLM response: {raw_text[:200]}...")
            
            # Extract JSON block
            json_text = _extract_json_block(raw_text)
            
            # Parse JSON
            try:
                parsed_json = json.loads(json_text)
            except json.JSONDecodeError as e:
                logger.warning(f"[JSON_IO] Attempt {attempt + 1} - JSON decode error: {e}")
                if attempt == retries:
                    raise JsonParseError(f"Failed to parse JSON after {retries + 1} attempts. Last error: {e}")
                continue
            
            # Validate against schema
            try:
                validate(instance=parsed_json, schema=schema)
                logger.info(f"[JSON_IO] Attempt {attempt + 1} - Successfully parsed and validated JSON")
                return parsed_json
            except ValidationError as e:
                logger.warning(f"[JSON_IO] Attempt {attempt + 1} - Schema validation error: {e.message}")
                if attempt == retries:
                    raise JsonParseError(f"JSON validation failed after {retries + 1} attempts. Last error: {e.message}")
                
                # Add schema hint to prompt for retry
                prompt += f"\n\nIMPORTANT: Your JSON must match this exact schema: {json.dumps(schema, indent=2)}"
                continue
                
        except Exception as e:
            logger.error(f"[JSON_IO] Attempt {attempt + 1} - Unexpected error: {e}")
            if attempt == retries:
                raise JsonParseError(f"Unexpected error after {retries + 1} attempts: {e}")
    
    # Should never reach here
    raise JsonParseError(f"Failed to get valid JSON after {retries + 1} attempts")
