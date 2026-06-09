"""Generate a social caption + hashtags for a clip.

Uses OpenAI when available (catchy, hook-first); otherwise falls back to a transcript-derived
hook plus the niche's configured hashtags. Fully offline-safe.
"""
from __future__ import annotations

from . import llm

_SYSTEM = (
    "You write short, punchy captions for vertical short-form clips cut from a longer video for a "
    "multi-account content farm. One line, hook first, no emoji spam, no clickbait lies. Subtly "
    "tease that there's more and nudge a follow for the full video / next part. Write the caption "
    "in the SAME language as the transcript."
)


def _hook(text: str, n: int = 12) -> str:
    return " ".join(text.split()[:n]).strip()


def _norm_tags(tags) -> list[str]:
    seen, out = set(), []
    for t in tags:
        t = str(t).strip()
        if not t:
            continue
        t = t if t.startswith("#") else "#" + t.lstrip("#")
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def caption_and_hashtags(text: str, niche_hashtags, *, model=None, niche_name: str = ""):
    """Return (caption, hashtags). Falls back to a transcript hook when OpenAI is unavailable."""
    base = list(niche_hashtags or [])
    if not text:
        return "", _norm_tags(base)
    if not llm.available():
        return _hook(text), _norm_tags(base)
    try:
        data = llm.chat_json([
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": (
                f"Niche: {niche_name}. Clip transcript: {text[:1200]}\n\n"
                'Return JSON {"caption": "<one-line hook>", "hashtags": ["#tag", ...]} '
                "with 5-8 relevant hashtags."
            )},
        ], model=model)
        caption = str(data.get("caption", "")).strip() or _hook(text)
        tags = _norm_tags(list(data.get("hashtags", [])) + base)[:10]
        return caption, tags or _norm_tags(base)
    except Exception:
        return _hook(text), _norm_tags(base)


def _offline_variant(text: str, base: list[str], i: int):
    """Deterministic per-account variation without an LLM: vary hook length + rotate hashtags."""
    words = text.split()
    caption = " ".join(words[: 10 + (i * 2) % 6]).strip() or _hook(text)
    tags = (base[i % len(base):] + base[: i % len(base)]) if base else []
    return caption, list(tags)


def caption_variants(text: str, niche_hashtags, accounts, *, model=None, niche_name: str = ""):
    """Return {account: (caption, hashtags)} with a DISTINCT caption per account.

    Identical captions/hashtags across accounts are a duplicate-content (shadowban) signal, so
    each account gets varied text. OpenAI makes truly distinct variants; the offline fallback
    varies hook length and rotates hashtags deterministically.
    """
    base = _norm_tags(niche_hashtags or [])
    accounts = list(accounts)
    if not text or not accounts:
        return {a: ("", list(base)) for a in accounts}
    if not llm.available():
        return {a: _offline_variant(text, base, i) for i, a in enumerate(accounts)}
    try:
        data = llm.chat_json([
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": (
                f"Niche: {niche_name}. Clip transcript: {text[:1200]}\n\n"
                f"Write {len(accounts)} DISTINCT one-line captions for the SAME clip posted to "
                f"{len(accounts)} different accounts — vary the wording/angle so they are NOT "
                'duplicates. Return JSON {"variants": [{"caption": "<str>", "hashtags": '
                '["#tag", ...]}]} with exactly that many items, 5-8 hashtags each.'
            )},
        ], model=model)
        variants = data.get("variants", [])
        out = {}
        for i, account in enumerate(accounts):
            v = variants[i] if i < len(variants) else {}
            caption = str(v.get("caption", "")).strip() or _offline_variant(text, base, i)[0]
            tags = _norm_tags(list(v.get("hashtags", [])) + base)[:10] or list(base)
            out[account] = (caption, tags)
        return out
    except Exception:
        return {a: _offline_variant(text, base, i) for i, a in enumerate(accounts)}
