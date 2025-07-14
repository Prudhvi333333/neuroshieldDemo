# import vertexai
# from vertexai.generative_models import GenerativeModel

# import os

# import json

# # You might also have other LLM utility functions here...
# PROJECT_ID = "fqkmwqpb-61mr-00mp-3824-ymblnk"
# LOCATION = "global"
# MODEL_NAME = "gemini-2.5-pro"


# def call_llm(prompt, system_msg="You are a helpful assistant."):
#     """
#     Calls Gemini via Vertex AI using project credentials (no API key needed in Cloud Shell).
#     """
#     try:
#         vertexai.init(project=PROJECT_ID, location=LOCATION)
#         model = GenerativeModel(MODEL_NAME)
#         full_prompt = f"{system_msg}\n\n{prompt}"
#         response = model.generate_content(full_prompt)
#         if hasattr(response, 'text') and response.text:
#             return response.text.strip()
#         else:
#             return "No response generated."
#     except Exception as e:
#         print(f"Vertex AI Gemini call failed: {e}")
#         return f"Error: {str(e)}"


# def call_llm_with_json_response(prompt):
#     """
#     Calls the LLM and expects a JSON response, ensuring correct content formatting.
#     """
#     try:
#         vertexai.init(project=PROJECT_ID, location=LOCATION)
#         model = GenerativeModel(MODEL_NAME)

#         # Corrected:
#         # 1. Removed the unnecessary "model" priming turn. The response_mime_type handles JSON output.
#         # 2. Ensured the user prompt is correctly wrapped in a {"text": "..."} dictionary
#         #    to be a proper 'Part' representation.
#         response = model.generate_content(
#             contents=[
#                 {"role": "user", "parts": [{"text": prompt}]},  # Fix: Wrap 'prompt' in {"text": ...}
#             ],
#             generation_config={
#                 "response_mime_type": "application/json",
#                 "temperature": 0.0,  # Often useful to set temperature low for structured output
#             },
#         )

#         # For debugging, it's better to print the response object itself or its attributes carefully
#         # as 'response.text' might not exist if the call failed or returned structured data directly.
#         # If response_mime_type="application/json" is used, response.text should contain the JSON string.
#         print(f"Raw response from Gemini (response.text attribute): {response.text}")

#         # Ensure the response.text is not empty or None before attempting to parse
#         if not response.text:
#             raise ValueError("Gemini returned an empty response for JSON.")

#         json_string = response.text.strip()

#         # Robust JSON parsing:
#         try:
#             parsed_json = json.loads(json_string)
#             return parsed_json
#         except json.JSONDecodeError as json_err:
#             print(f"Failed to decode JSON from Gemini response: {json_err}")
#             print(f"Attempted to parse: '{json_string}'")
#             return {"error": f"JSON decoding failed: {json_err}", "raw_response": json_string}

#     except Exception as e:
#         print(f"Vertex AI Gemini call with JSON response failed: {e}")
#         return {"error": str(e)}  # Return an error dictionary for consistency

"""
Centralised helpers for talking to Gemini on Vertex AI.
"""
 
from __future__ import annotations
 
import json
from typing import Any, Dict, List
 
from google import genai
from google.genai import types
 
PROJECT_ID = "fqkmwqpb-61mr-00mp-3824-ymblnk"   # ← change me
LOCATION = "global"
MODEL_NAME = "gemini-2.5-flash"
 
# single shared client
_client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
 
 
def _mk_config(json_mode: bool = False) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        temperature=0.0,
        top_p=1.0,
        max_output_tokens=4096,
        response_mime_type="application/json" if json_mode else "text/plain",
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
    )
 
 
def _call_gemini(parts: List[types.Part], json_mode: bool) -> str:
    cfg = _mk_config(json_mode)
    for chunk in _client.models.generate_content_stream(
        model=MODEL_NAME,
        contents=[types.Content(role="user", parts=parts)],
        config=cfg,
    ):
        # stream mode, but we just concat
        if chunk.text:
            yield chunk.text
 
 
def call_llm(prompt: str, system_msg: str = "You are a helpful assistant.") -> str:
    full_prompt = f"{system_msg}\n\n{prompt}"
    return "".join(_call_gemini([types.Part.from_text(text=full_prompt)], json_mode=False)).strip()
 
 
def call_llm_with_json_response(prompt: str) -> Dict[str, Any]:
    raw = "".join(_call_gemini([types.Part.from_text(text=prompt)], json_mode=True)).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "Gemini JSON parse failure", "raw": raw}