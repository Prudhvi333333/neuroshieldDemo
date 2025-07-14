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

import vertexai
from vertexai.generative_models import GenerativeModel

import os

PROJECT_ID = "PROJECT_ID"
LOCATION = "global"
MODEL_NAME = "gemini-2.5-flash"  # Or "gemini-1.5-pro"


def call_llm(prompt, system_msg="You are a helpful assistant."):
    """
    Calls Gemini via Vertex AI using project credentials (no API key needed in Cloud Shell).
    """
    try:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        model = GenerativeModel(MODEL_NAME)
        full_prompt = f"{system_msg}\n\n{prompt}"
        response = model.generate_content(full_prompt)
        if hasattr(response, 'text') and response.text:
            return response.text.strip()
        else:
            return "No response generated."
    except Exception as e:
        print(f"Vertex AI Gemini call failed: {e}")
        return f"Error: {str(e)}"