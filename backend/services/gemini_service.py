"""
Gemini 共用工具 — 所有 routers 透過此呼叫 gemini-2.5-flash-lite
"""
from core.config import GEMINI_API_KEY


def ask_gemini(prompt: str, model: str = "gemini-2.5-flash-lite-preview-06-17") -> str:
    from google import genai as _genai
    client = _genai.Client(api_key=GEMINI_API_KEY)
    resp = client.models.generate_content(model=model, contents=prompt)
    return resp.text
