import asyncio
import re

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


# Whole-word keyword tables (longest list first). Word boundaries prevent
# false positives like "errors" matching "error" — but "errors" also matches
# anyway because of \b on both sides of the alternation. Phrases like
# "data loss" are matched as substrings since \b around multi-word phrases
# behaves correctly.
_KW_CRITICAL = re.compile(
    r"\b(critical|crash|crashes|crashing|security|vulnerab\w*|"
    r"breaking\s+change|breaking|data\s+loss|exploit|injection|leak\w*|"
    r"panic|deadlock|race\s+condition|oom|segfault)\b",
    re.IGNORECASE,
)
_KW_BUG = re.compile(
    r"\b(bug|error|errors|incorrect|wrong|broken|fails?|failing|"
    r"exception|exceptions|throws|null\s+pointer|undefined\s+behavior|"
    r"off[-\s]by[-\s]one|regression)\b",
    re.IGNORECASE,
)
_KW_SUGGESTION = re.compile(
    r"\b(consider|maybe|could|might|perhaps|suggestion|"
    r"nit|nitpick|nitpicky|style|formatting|typo|rename|naming|readability)\b",
    re.IGNORECASE,
)


def classify_by_keywords(body: str) -> int:
    """Deterministic offline classifier. Used when the LLM is unconfigured
    or fails. Resolves to the highest matching severity, since one critical
    keyword in a long comment should not be diluted by lower-severity ones."""
    if not body:
        return 0
    if _KW_CRITICAL.search(body):
        return 5
    if _KW_BUG.search(body):
        return 3
    if _KW_SUGGESTION.search(body):
        return 0
    return 1


async def classify_comment(comment_body: str) -> int:
    if not OPENROUTER_API_KEY:
        return classify_by_keywords(comment_body)
    try:
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
            return classify_by_keywords(comment_body)
        raw = result["choices"][0]["message"]["content"].strip()
        if raw in ("0", "1", "3", "5"):
            return int(raw)
        return classify_by_keywords(comment_body)
    except (httpx.HTTPError, ValueError, KeyError):
        return classify_by_keywords(comment_body)


async def classify_many(bodies: list[str]) -> list[int]:
    if not bodies:
        return []
    return await asyncio.gather(*(classify_comment(b) for b in bodies))
