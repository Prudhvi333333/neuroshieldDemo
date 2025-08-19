# from google import genai
# from google.genai import types
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
import os

# Load environment variables from .env file early
load_dotenv()

import google.generativeai as genai
from llm_utils import call_llm_json

# from google import genai
# from google.genai import types
# import base64

# def generate():
#   client = genai.Client(
#       vertexai=True,
#       project="fqkmwqpb-61mr-00mp-3824-ymblnk",
#       location="global",
#   )


#   model = "gemini-2.5-flash"
#   contents = [
#     types.Content(
#       role="user",
#       parts=[
#         types.Part.from_text(text="""What is LLM""")
#       ]
#     )
#   ]

#   generate_content_config = types.GenerateContentConfig(
#     temperature = 1,
#     top_p = 1,
#     seed = 0,
#     max_output_tokens = 65535,
#     safety_settings = [types.SafetySetting(
#       category="HARM_CATEGORY_HATE_SPEECH",
#       threshold="OFF"
#     ),types.SafetySetting(
#       category="HARM_CATEGORY_DANGEROUS_CONTENT",
#       threshold="OFF"
#     ),types.SafetySetting(
#       category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
#       threshold="OFF"
#     ),types.SafetySetting(
#       category="HARM_CATEGORY_HARASSMENT",
#       threshold="OFF"
#     )],
#     thinking_config=types.ThinkingConfig(
#       thinking_budget=-1,
#     ),
#   )

#   for chunk in client.models.generate_content_stream(
#     model = model,
#     contents = contents,
#     config = generate_content_config,
#     ):
#     print(chunk.text, end="")

# generate()


API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("Fatal: GOOGLE_API_KEY not found. Ensure it is set in the .env file located in the project root.")

genai.configure(api_key=API_KEY)

MODEL_NAME = os.getenv("GOOGLE_MODEL_NAME", "gemini-pro")

def call_llm(prompt: str, system_msg: str = "You are a helpful assistant.") -> str:
    """
    Calls Gemini via google-generativeai using the provided API key.
    """
    full_prompt = f"{system_msg}\n\n{prompt}"
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(full_prompt)
        if hasattr(response, 'text') and response.text:
            return response.text.strip()
        return "No response generated."
    except Exception as e:
        print(f"Generative AI Gemini call failed: {e}")
        return f"Error: {str(e)}"