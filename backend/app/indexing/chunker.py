from __future__ import annotations

from typing import Iterable

CHUNK_SIZE = 800
OVERLAP = 100
SEPARATORS = ("\n\n", "\n", ". ", " ")


def _split(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            for sep in SEPARATORS:
                idx = text.rfind(sep, start + size // 2, end)
                if idx != -1:
                    end = idx + len(sep)
                    break
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def chunk_interaction(subject: str | None, body: str | None) -> list[str]:
    body = (body or "").strip()
    subject = (subject or "").strip()
    base = f"{subject}\n\n{body}".strip() if subject else body
    if not base:
        return []
    if len(base) <= CHUNK_SIZE:
        return [base]
    return _split(base, CHUNK_SIZE, OVERLAP)


def chunk_profile_summary(summary: str | None) -> list[str]:
    s = (summary or "").strip()
    if not s:
        return []
    return [s[:2000]]
