import asyncio
import json
from typing import Any

import httpx
from fastapi import HTTPException

from ..core.config import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-3.3-70b-instruct:free"

SYSTEM_PROMPT = """You are an expert meeting analyst. Analyze the meeting report and extract structured information.
Respond ONLY with a valid JSON object, no explanation, no markdown, no backticks.
The JSON must have exactly these fields:
{
  "language": "fr" or "en",
  "resume": "2-3 sentence summary of the meeting",
  "decisions": ["decision 1", "decision 2", ...],
  "actions": [
    {"action": "what to do", "responsible": "person name or team", "deadline": "deadline if mentioned or null"},
    ...
  ],
  "blocages": ["blocage or risk 1", "blocage or risk 2", ...]
}
If a field has no content, use an empty array [] or empty string "".
Respond in the same language as the meeting report."""

_MAX_RETRIES = 4
_BASE_DELAY = 12  # seconds


async def analyze_compte_rendu(raw_text: str) -> dict[str, Any]:
    if not settings.openrouter_api_key:
        return {
            "language": "fr",
            "resume": "LLM not configured.",
            "decisions": [],
            "actions": [],
            "blocages": []
        }

    last_error = None
    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(_MAX_RETRIES):
            response = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": raw_text}
                    ],
                    "max_tokens": 1000,
                }
            )
            result = response.json()

            if response.status_code == 429:
                meta = result.get("error", {}).get("metadata", {})
                retry_after = meta.get("retry_after_seconds", _BASE_DELAY)
                last_error = result.get("error", {}).get("message", "Rate limited")
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(float(retry_after))
                continue

            if "choices" not in result:
                raise HTTPException(
                    status_code=502,
                    detail=f"OpenRouter error: {result.get('error', result)}"
                )

            raw = result["choices"][0]["message"]["content"].strip()
            # strip markdown backticks if model adds them
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            try:
                return json.loads(raw.strip())
            except Exception:
                return {"language": "fr", "resume": raw, "decisions": [], "actions": [], "blocages": []}

    raise HTTPException(
        status_code=429,
        detail=f"LLM upstream rate-limited after {_MAX_RETRIES} retries: {last_error}"
    )
