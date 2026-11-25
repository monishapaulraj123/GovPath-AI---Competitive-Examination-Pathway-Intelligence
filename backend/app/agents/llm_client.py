"""
Optional External LLM Integration Client (OpenAI / Gemini) with graceful grounded fallback.
"""

from typing import Optional
import requests
from app.config import get_settings


def get_llm_status() -> dict:
    settings = get_settings()
    if settings.OPENAI_API_KEY:
        return {"configured": True, "provider": "openai", "model": settings.OPENAI_MODEL}
    if settings.GEMINI_API_KEY:
        return {"configured": True, "provider": "gemini", "model": settings.GEMINI_MODEL}
    return {
        "configured": False,
        "provider": "grounded_deterministic",
        "model": "GovPath Grounded Synthesis Engine",
    }


def generate_llm_response(system_prompt: str, user_prompt: str) -> Optional[str]:
    settings = get_settings()

    if settings.OPENAI_API_KEY and settings.LLM_PROVIDER in ("auto", "openai"):
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.OPENAI_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.25,
                    "max_tokens": 900,
                },
                timeout=20,
            )
            if resp.ok:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return None

    if settings.GEMINI_API_KEY and settings.LLM_PROVIDER in ("auto", "gemini"):
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
            )
            resp = requests.post(
                url,
                json={
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                    "generationConfig": {"temperature": 0.25, "maxOutputTokens": 900},
                },
                timeout=20,
            )
            if resp.ok:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            return None

    return None
