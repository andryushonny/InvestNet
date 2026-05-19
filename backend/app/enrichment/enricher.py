from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlmodel import select

from ..core.state import state
from ..db.models import Interaction, InvestmentProfile, Person
from ..db.session import get_session
from ..indexing import indexer
from ..llm import gateway
from .web import fetch_url_text, web_search


SYSTEM = (
    "Ты аналитик, формирующий профиль потенциального инвестора по доступным данным. "
    "Возвращай только валидный JSON без markdown-обёрток."
)


def _build_user_prompt(person: Person, recent: list[Interaction], web: list[dict]) -> str:
    emails_summary = []
    for ia in recent[:10]:
        snippet = (ia.body_cleaned or "")[:500]
        emails_summary.append(
            f"- [{ia.occurred_at.isoformat() if ia.occurred_at else ''}] {ia.direction} | {(ia.subject or '')[:120]}\n  {snippet}"
        )
    web_summary = []
    for w in web:
        web_summary.append(f"### {w.get('title') or w.get('url')}\nURL: {w.get('url')}\n{w.get('text', '')[:2000]}")

    return f"""Данные о персоне:
Имя: {person.full_name}
Компания: {person.company or ''}
Должность: {person.title or ''}
Email: {person.primary_email or ''}
LinkedIn: {person.linkedin_url or ''}

Последние взаимодействия:
{chr(10).join(emails_summary) or 'нет'}

Публичные находки:
{chr(10).join(web_summary) or 'нет'}

Верни строго следующий JSON:
{{
  "investment_interests": ["сектор1", "сектор2"],
  "preferred_ticket": "диапазон в USD или null",
  "geography": ["страна или регион"],
  "stage_focus": ["pre-seed", "seed", "series A"],
  "keywords": ["semantic-маркер1"],
  "ai_summary": "3-5 предложений о человеке и его инвестиционных интересах",
  "confidence": 0.0,
  "extracted_evidence": ["цитата 1", "цитата 2"]
}}

Если данных недостаточно — выставь confidence ≤ 0.3 и заполни поля null/[] где невозможно вывести."""


async def enrich_person(person_id: int) -> Optional[InvestmentProfile]:
    s = state.settings
    model = s.models.enrichment if s else "deepseek/deepseek-chat-v3.5:free"

    with get_session() as session:
        person = session.get(Person, person_id)
        if not person:
            return None
        ias = session.exec(
            select(Interaction).where(Interaction.person_id == person_id).order_by(Interaction.occurred_at.desc())
        ).all()[:20]

    if len(ias) < 3 and not (person.company or person.title):
        logger.info(f"skip enrichment {person_id}: low signal")
        return None

    # Web search
    query_parts = [person.full_name]
    if person.company:
        query_parts.append(person.company)
    query_parts.append("investor OR angel OR fund")
    query = " ".join(query_parts)
    hits = await web_search(query, max_results=5)
    fetched: list[dict] = []
    if hits:
        urls = [h.get("href") or h.get("url") for h in hits if (h.get("href") or h.get("url"))]
        texts = await asyncio.gather(*[fetch_url_text(u) for u in urls[:5]], return_exceptions=True)
        for u, t, h in zip(urls, texts, hits):
            if isinstance(t, str) and t:
                fetched.append({"url": u, "title": h.get("title", ""), "text": t})

    user_prompt = _build_user_prompt(person, ias, fetched)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_prompt}]
    try:
        result = await gateway.chat_json(messages, model=model)
    except Exception as e:
        logger.error(f"enrichment LLM failed for {person_id}: {e}")
        return None

    profile = InvestmentProfile(
        person_id=person_id,
        investment_interests=json.dumps(result.get("investment_interests") or [], ensure_ascii=False),
        preferred_ticket=result.get("preferred_ticket"),
        geography=json.dumps(result.get("geography") or [], ensure_ascii=False),
        stage_focus=json.dumps(result.get("stage_focus") or [], ensure_ascii=False),
        keywords=json.dumps(result.get("keywords") or [], ensure_ascii=False),
        ai_summary=result.get("ai_summary"),
        confidence=float(result.get("confidence") or 0.0),
        sources=json.dumps({"web": [f["url"] for f in fetched], "interactions": [ia.id for ia in ias]}, ensure_ascii=False),
        enriched_at=datetime.utcnow(),
        raw_enrichment_data=json.dumps({"web": fetched, "llm_response": result}, ensure_ascii=False)[:200_000],
    )
    with get_session() as session:
        existing = session.get(InvestmentProfile, person_id)
        if existing:
            for k, v in profile.model_dump().items():
                setattr(existing, k, v)
            session.add(existing)
        else:
            session.add(profile)
        session.commit()

    try:
        await indexer.index_profile(person_id)
    except Exception as e:
        logger.warning(f"profile index failed {person_id}: {e}")

    return profile


async def enrich_batch(person_ids: list[int], progress_cb=None, concurrency: int = 3) -> dict:
    sem = asyncio.Semaphore(concurrency)
    stats = {"done": 0, "failed": 0, "skipped": 0}

    async def go(pid):
        async with sem:
            try:
                prof = await enrich_person(pid)
                if prof:
                    stats["done"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                logger.exception(f"enrich {pid} error: {e}")
                stats["failed"] += 1
            if progress_cb:
                progress_cb((stats["done"] + stats["failed"] + stats["skipped"]) / len(person_ids), stats)

    await asyncio.gather(*[go(pid) for pid in person_ids])
    return stats
