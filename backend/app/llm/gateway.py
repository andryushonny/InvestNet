from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx
from loguru import logger

from ..core.state import state


class LLMError(RuntimeError):
    pass


def _provider_endpoint(provider: str, settings) -> tuple[str, str]:
    if provider == "openai":
        return settings.openai_base_url, settings.api_key
    return settings.openrouter_base_url, settings.api_key


def _embed_endpoint(settings) -> tuple[str, str]:
    if settings.embedding_provider == "openai":
        key = settings.embedding_api_key or settings.api_key if settings.provider == "openai" else settings.embedding_api_key
        return settings.openai_base_url, key
    key = settings.embedding_api_key or settings.api_key
    return settings.openrouter_base_url, key


async def _post_json(url: str, headers: dict, payload: dict, timeout: float = 120.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as cli:
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                r = await cli.post(url, headers=headers, json=payload)
                if r.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning(f"rate-limited, retry in {wait}s")
                    await asyncio.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"LLM HTTP {e.response.status_code}: {e.response.text[:500]}")
                last_err = e
                if e.response.status_code >= 500:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise LLMError(f"HTTP {e.response.status_code}: {e.response.text[:300]}") from e
            except httpx.HTTPError as e:
                last_err = e
                await asyncio.sleep(2 ** attempt)
        raise LLMError(f"LLM call failed after retries: {last_err}")


def _headers(api_key: str, referer: str = "https://investnet.local") -> dict:
    h = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if "openrouter" in referer or True:
        h["HTTP-Referer"] = referer
        h["X-Title"] = "InvestNet"
    return h


async def chat(messages: list[dict], model: str | None = None, **kwargs) -> str:
    s = state.settings
    if not s or not s.api_key:
        raise LLMError("API key not configured")
    base, key = _provider_endpoint(s.provider, s)
    model = model or s.models.enrichment
    payload = {"model": model, "messages": messages, **kwargs}
    data = await _post_json(f"{base}/chat/completions", _headers(key), payload)
    return data["choices"][0]["message"]["content"]


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


async def chat_json(messages: list[dict], model: str | None = None, **kwargs) -> Any:
    kwargs.setdefault("response_format", {"type": "json_object"})
    try:
        raw = await chat(messages, model=model, **kwargs)
    except LLMError:
        kwargs.pop("response_format", None)
        raw = await chat(messages, model=model, **kwargs)
    return _extract_json(raw)


async def embed(texts: list[str], model: str | None = None) -> list[list[float]]:
    s = state.settings
    if not texts:
        return []
    if not s:
        raise LLMError("Settings not initialised")
    base, key = _embed_endpoint(s)
    if not key:
        raise LLMError("Embedding API key not configured")
    model = model or s.models.embedding
    payload: dict = {"model": model, "input": texts}
    if model.startswith("text-embedding-3"):
        payload["dimensions"] = 512
    data = await _post_json(f"{base}/embeddings", _headers(key), payload)
    return [d["embedding"] for d in data["data"]]
