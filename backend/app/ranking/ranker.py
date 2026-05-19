from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlmodel import select

from ..core.state import state
from ..db.models import Deal, Interaction, InvestmentCase, InvestmentProfile, Person
from ..db.session import get_session
from ..indexing import vector_store
from ..llm import gateway


SYSTEM = (
    "Ты оцениваешь, насколько потенциальный инвестор заинтересуется конкретным кейсом. "
    "Отвечай строго JSON."
)


def _person_profile_block(person: Person, profile: Optional[InvestmentProfile]) -> str:
    interests = []
    geography = []
    stages = []
    summary = ""
    ticket = ""
    if profile:
        interests = json.loads(profile.investment_interests or "[]")
        geography = json.loads(profile.geography or "[]")
        stages = json.loads(profile.stage_focus or "[]")
        summary = profile.ai_summary or ""
        ticket = profile.preferred_ticket or ""
    return (
        f"Имя: {person.full_name} | Должность: {person.title or ''} @ {person.company or ''}\n"
        f"Резюме AI: {summary}\n"
        f"Интересы: {interests}\n"
        f"Чек: {ticket}\n"
        f"География: {geography}\n"
        f"Стадии: {stages}"
    )


def _recent_block(recent: list[Interaction]) -> str:
    lines = []
    for ia in recent[:5]:
        snippet = (ia.body_cleaned or "")[:300].replace("\n", " ")
        lines.append(f"- [{ia.occurred_at.date() if ia.occurred_at else ''}] {ia.direction}: {snippet}")
    return "\n".join(lines) or "нет"


def _build_prompt(case: InvestmentCase, person: Person, profile: Optional[InvestmentProfile], recent: list[Interaction]) -> str:
    return f"""Кейс:
Заголовок: {case.title}
Описание: {case.description}
Стадия: {case.stage or ''}
Чек: {case.ticket_range or ''}
Сектор: {case.sector or ''}
География: {case.geography or ''}

Профиль персоны:
{_person_profile_block(person, profile)}

Недавние касания (последние 5):
{_recent_block(recent)}

Верни JSON:
{{
  "score": <0-100>,
  "match_reasons": ["причина 1", "причина 2"],
  "risks": ["потенциальный стоп-фактор"],
  "recommended_angle": "одно предложение: как лучше подойти к этому человеку"
}}

Калибровка score:
- 80-100: явный match по сектору + стадии + чеку, есть тёплый контакт.
- 50-79: частичный match, разумно написать.
- 20-49: косвенный интерес, низкий приоритет.
- 0-19: нерелевантно."""


async def _score_candidate(case: InvestmentCase, pid: int, model: str) -> Optional[tuple[int, float, dict]]:
    with get_session() as session:
        person = session.get(Person, pid)
        if not person:
            return None
        profile = session.get(InvestmentProfile, pid)
        recent = session.exec(
            select(Interaction).where(Interaction.person_id == pid).order_by(Interaction.occurred_at.desc())
        ).all()[:5]
    prompt = _build_prompt(case, person, profile, recent)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    try:
        result = await gateway.chat_json(messages, model=model)
    except Exception as e:
        logger.error(f"rank {pid}: {e}")
        return None
    score = float(result.get("score", 0))
    return pid, score, result


async def rank_case(case_id: int, top_n_candidates: int = 100, progress_cb=None) -> list[dict]:
    with get_session() as session:
        case = session.get(InvestmentCase, case_id)
        if not case:
            raise ValueError("case not found")

    s = state.settings
    model_rank = s.models.ranking if s else "deepseek/deepseek-chat-v3.5:free"

    case_text = f"{case.title}\n\n{case.description}\nСектор: {case.sector or ''}\nСтадия: {case.stage or ''}\nГеография: {case.geography or ''}"
    case_vec = (await gateway.embed([case_text]))[0]

    profile_hits = vector_store.profiles().search(case_vec, top_k=top_n_candidates)
    interaction_hits = vector_store.interactions().search(case_vec, top_k=top_n_candidates * 2)

    seen = []
    seen_set: set[int] = set()
    for _fid, _d, md in profile_hits + interaction_hits:
        pid = int(md["person_id"])
        if pid in seen_set:
            continue
        seen_set.add(pid)
        seen.append(pid)
        if len(seen) >= top_n_candidates:
            break

    if not seen:
        return []

    sem = asyncio.Semaphore(5)
    results: list[tuple[int, float, dict]] = []
    done_count = 0

    async def go(pid: int):
        nonlocal done_count
        async with sem:
            r = await _score_candidate(case, pid, model_rank)
        done_count += 1
        if progress_cb:
            progress_cb(done_count / len(seen), {"scored": done_count})
        if r:
            results.append(r)

    await asyncio.gather(*[go(p) for p in seen])

    results.sort(key=lambda x: x[1], reverse=True)

    out: list[dict] = []
    with get_session() as session:
        for pid, score, reasoning in results:
            deal = session.exec(
                select(Deal).where(Deal.person_id == pid, Deal.case_id == case_id)
            ).first()
            if deal:
                deal.score = score
                deal.reasoning = json.dumps(reasoning, ensure_ascii=False)
                deal.updated_at = datetime.utcnow()
            else:
                deal = Deal(
                    person_id=pid,
                    case_id=case_id,
                    score=score,
                    reasoning=json.dumps(reasoning, ensure_ascii=False),
                    status="new",
                )
                session.add(deal)
            session.commit()
            session.refresh(deal)
            out.append({
                "deal_id": deal.id,
                "person_id": pid,
                "score": score,
                "reasoning": reasoning,
            })
    return out
