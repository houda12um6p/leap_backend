import asyncio

import httpx
from ..core.config import settings

OPENROUTER_API_KEY = settings.openrouter_api_key
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-3.3-70b-instruct:free"
MAX_CONCURRENCY = settings.llm_max_concurrency

_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

SYSTEM_PROMPT = """You are a code review severity classifier. Classify the comment into exactly one category.

Categories:
- 0: suggestion (style, naming, readability — no functional impact)
- 1: minor issue (missing check, small bug, non-critical)
- 3: correctness bug (wrong logic, incorrect behavior, bad data handling)
- 5: critical issue (security flaw, crash risk, data loss, breaking change)

Respond with ONLY the number: 0, 1, 3, or 5. No explanation."""


async def classify_comment(comment_body: str) -> int:
    if not OPENROUTER_API_KEY:
        return 1
    async with _semaphore:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": comment_body},
                    ],
                    "max_tokens": 5,
                },
            )
        result = response.json()
        if "choices" not in result:
            return 1
        raw = result["choices"][0]["message"]["content"].strip()
        return int(raw) if raw in ("0", "1", "3", "5") else 1


async def classify_many(bodies: list[str]) -> list[int]:
    if not bodies:
        return []
    return await asyncio.gather(*(classify_comment(b) for b in bodies))
