from __future__ import annotations

import json
from typing import Optional

from loguru import logger
from sqlmodel import select

from ..core.state import state
from ..db.models import Deal, GeneratedEmailDraft, Interaction, InvestmentCase, InvestmentProfile, Person
from ..db.session import get_session
from ..llm import gateway


SYSTEM = """Ты пишешь первое деловое письмо потенциальному инвестору от имени основателя.
Правила:
- 130–200 слов.
- Без шаблонных вступлений ("I hope this email finds you well", "Trust this finds you well").
- Обязательно сослаться на конкретный факт: или из истории общения, или из публичного профиля.
- Тон: уверенный, уважительный, не продающий.
- В конце — один конкретный CTA: 15-минутный звонок / короткий ответ да/нет / отправка одностраничника.
- Если язык переписки или origin = русский → пиши на русском, иначе на английском.
Верни JSON: {"subject": "...", "body": "..."}."""


def _last_interaction_summary(recent: list[Interaction]) -> str:
    if not recent:
        return "нет"
    ia = recent[0]
    snippet = (ia.body_cleaned or "")[:300].replace("\n", " ")
    return f"[{ia.occurred_at.date() if ia.occurred_at else ''}] {ia.direction} | {(ia.subject or '')[:100]} — {snippet}"


async def compose_for_deal(deal_id: int) -> Optional[GeneratedEmailDraft]:
    with get_session() as session:
        deal = session.get(Deal, deal_id)
        if not deal:
            return None
        person = session.get(Person, deal.person_id)
        case = session.get(InvestmentCase, deal.case_id)
        profile = session.get(InvestmentProfile, deal.person_id)
        recent = session.exec(
            select(Interaction).where(Interaction.person_id == deal.person_id).order_by(Interaction.occurred_at.desc())
        ).all()[:5]

    if not person or not case:
        return None

    interests = []
    summary = ""
    if profile:
        interests = json.loads(profile.investment_interests or "[]")
        summary = profile.ai_summary or ""

    reasoning = {}
    if deal.reasoning:
        try:
            reasoning = json.loads(deal.reasoning)
        except Exception:
            reasoning = {}

    user_prompt = f"""Получатель: {person.full_name}, {person.title or ''} @ {person.company or ''}
Профиль: {summary}
Интересы: {interests}
Последнее касание: {_last_interaction_summary(recent)}
Кейс: {case.title}
Описание: {case.description}
Рекомендованный угол: {reasoning.get('recommended_angle', '')}"""

    s = state.settings
    model = s.models.composer if s else "deepseek/deepseek-chat-v3.5:free"
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_prompt}]
    try:
        result = await gateway.chat_json(messages, model=model)
    except Exception as e:
        logger.error(f"composer error deal={deal_id}: {e}")
        return None

    subj = (result.get("subject") or "").strip()[:200] or f"Re: {case.title}"
    body = (result.get("body") or "").strip()
    if not body:
        return None

    draft = GeneratedEmailDraft(deal_id=deal_id, subject=subj, body=body, model_used=model)
    with get_session() as session:
        session.add(draft)
        session.commit()
        session.refresh(draft)
    return draft
