from __future__ import annotations

import re

_TALON_READY = False


def _init_talon() -> None:
    global _TALON_READY
    if _TALON_READY:
        return
    try:
        import talon
        talon.init()
        _TALON_READY = True
    except Exception:
        _TALON_READY = False


_RU_QUOTE_HEADERS = re.compile(
    r"(^|\n)\s*(От|Отправлено|Кому|Тема|Дата):.*?(\n\n|\Z)",
    flags=re.IGNORECASE | re.DOTALL,
)
_GENERIC_QUOTE = re.compile(r"(^|\n)\s*>.*", flags=re.MULTILINE)


def clean_email_body(body: str) -> str:
    if not body:
        return ""
    _init_talon()
    text = body
    try:
        if _TALON_READY:
            from talon import quotations  # type: ignore
            from talon.signature.bruteforce import extract_signature
            text = quotations.extract_from_plain(text)
            text, _sig = extract_signature(text)
    except Exception:
        pass
    text = _RU_QUOTE_HEADERS.sub("\n", text)
    text = _GENERIC_QUOTE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:50_000]


def html_to_text(html: str) -> str:
    if not html:
        return ""
    try:
        from selectolax.parser import HTMLParser
        tree = HTMLParser(html)
        for tag in ("script", "style"):
            for node in tree.css(tag):
                node.decompose()
        text = tree.body.text(separator="\n") if tree.body else tree.text(separator="\n")
        return re.sub(r"\n{3,}", "\n\n", text).strip()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
