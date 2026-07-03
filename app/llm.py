"""
LLM client — Groq (llama-3.3-70b-versatile)

Groq offers a generous free tier with low-latency inference,
making it well suited for conversational recommendation tasks.

Environment variables:
  GROQ_API_KEY   (required)
  GROQ_MODEL     (optional, default: llama-3.3-70b-versatile)
"""
import json
import os
import httpx

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"


class LLMError(Exception):
    pass


async def generate_json(system_prompt: str, user_prompt: str, timeout: float = 22.0) -> dict:
    """
    Call Groq with forced JSON response mode.
    Returns a parsed dict.
    Raises LLMError on any failure so the caller can use its deterministic fallback.
    """
    if not GROQ_API_KEY:
        raise LLMError("GROQ_API_KEY is not set")

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "max_tokens": 1024,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(GROQ_URL, json=payload, headers=headers)
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return json.loads(text)
    except Exception as e:
        raise LLMError(f"Groq request failed: {e}") from e

    