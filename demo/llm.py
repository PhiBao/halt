"""Minimal DGrid AI Gateway client (OpenAI-compatible chat completions)."""
import os

import requests

BASE_URL = "https://api.dgrid.ai"
MODEL = "openai/gpt-4o-mini"


def chat(messages, model: str = MODEL, temperature: float = 0.2, max_tokens: int = 700) -> str:
    key = os.environ.get("DGRID_API_KEY")
    if not key:
        raise RuntimeError("Set DGRID_API_KEY env var (see .env)")
    r = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
