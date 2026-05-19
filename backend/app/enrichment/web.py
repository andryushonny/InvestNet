from __future__ import annotations

import asyncio
from typing import Any

import httpx
from loguru import logger


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo search via ddgs library, off-thread."""
    def _go():
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS  # legacy package
            except Exception:
                return []
        try:
            with DDGS() as d:
                return list(d.text(query, max_results=max_results))
        except Exception as e:
            logger.warning(f"ddgs error: {e}")
            return []
    return await asyncio.to_thread(_go)


async def fetch_url_text(url: str, timeout: float = 5.0, max_bytes: int = 200_000) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 InvestNet/1.0"
        }) as cli:
            r = await cli.get(url)
            r.raise_for_status()
            content = r.content[:max_bytes]
            ctype = r.headers.get("content-type", "")
            if "html" not in ctype and "text" not in ctype:
                return ""
            from selectolax.parser import HTMLParser
            tree = HTMLParser(content)
            for tag in ("script", "style", "nav", "footer"):
                for n in tree.css(tag):
                    n.decompose()
            body = tree.body
            text = (body.text(separator="\n") if body else tree.text(separator="\n")).strip()
            return text[:5000]
    except Exception as e:
        logger.debug(f"fetch {url}: {e}")
        return ""
