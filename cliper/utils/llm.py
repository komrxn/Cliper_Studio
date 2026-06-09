"""OpenAI API wrapper for Cliper's AI reasoning layer (moment selection + clip QA).

The media pipeline is self-hosted, but a strong LLM won't fit the local 8 GB GPU, so the
*reasoning* layer calls OpenAI. Transcription stays local (faster-whisper). Configure with
OPENAI_API_KEY (required) and optionally CLIPER_OPENAI_MODEL. All imports are lazy so the
offline heuristic path never needs the openai package or a key.
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

DEFAULT_MODEL = os.environ.get("CLIPER_OPENAI_MODEL", "gpt-4o-mini")


class LLMError(RuntimeError):
    """Raised on missing key/package or repeated API failure."""


def available() -> bool:
    """True if an OpenAI client could be constructed (package + key present)."""
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("OPENAI_API_KEY"))


def _client():
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMError("openai package not installed — `pip install openai`") from exc
    if not os.environ.get("OPENAI_API_KEY"):
        raise LLMError("OPENAI_API_KEY is not set in the environment")
    return OpenAI()


def chat_json(messages: list[dict], *, model: str | None = None, retries: int = 3,
              temperature: float = 0.2) -> dict:
    """Call chat completions in JSON mode and return the parsed object (with backoff retries)."""
    client = _client()
    last: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model or DEFAULT_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=temperature,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as exc:  # network / rate-limit / parse — retry with backoff
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise LLMError(f"chat_json failed after {retries} attempts: {last}")


def image_block(path) -> dict:
    """A vision content block (base64 data URL) for a chat message."""
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}


def text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def as_float(v, default: float = 0.0) -> float:
    """Coerce a model-returned value to float (handles None / non-numeric -> default)."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def as_bool(v) -> bool:
    """Coerce a model-returned value to bool (handles the string 'false', 0, etc.)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return str(v).strip().lower() in ("true", "yes", "1")
