from __future__ import annotations

import asyncio
from typing import Iterable

from loguru import logger
from sqlmodel import select

from ..db.models import Interaction, InvestmentProfile
from ..db.session import get_session
from ..llm import gateway
from . import vector_store
from .chunker import chunk_interaction, chunk_profile_summary

BATCH = 64


async def _embed_in_batches(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    sem = asyncio.Semaphore(5)

    async def go(batch):
        async with sem:
            return await gateway.embed(batch)

    tasks = []
    for i in range(0, len(texts), BATCH):
        tasks.append(go(texts[i:i + BATCH]))
    results = await asyncio.gather(*tasks)
    for r in results:
        out.extend(r)
    return out


async def index_interactions(progress_cb=None) -> dict:
    store = vector_store.interactions()
    indexed_iids = set()
    cur = store.conn.execute("SELECT DISTINCT interaction_id FROM faiss_map WHERE interaction_id IS NOT NULL")
    indexed_iids = {r[0] for r in cur.fetchall()}

    pending_texts: list[str] = []
    pending_records: list[dict] = []
    stats = {"indexed": 0, "skipped": 0}

    with get_session() as session:
        ias = session.exec(select(Interaction)).all()
        total = len(ias)
        for idx, ia in enumerate(ias):
            if ia.id in indexed_iids:
                stats["skipped"] += 1
                continue
            chunks = chunk_interaction(ia.subject, ia.body_cleaned)
            for ci, text in enumerate(chunks):
                pending_texts.append(text)
                pending_records.append({
                    "text": text,
                    "person_id": ia.person_id,
                    "interaction_id": ia.id,
                    "metadata": {
                        "channel": ia.channel,
                        "direction": ia.direction,
                        "occurred_at": ia.occurred_at.isoformat() if ia.occurred_at else None,
                        "subject": ia.subject,
                        "chunk_index": ci,
                    },
                })

            if len(pending_texts) >= BATCH * 5:
                vecs = await _embed_in_batches(pending_texts)
                store.add(vecs, pending_records)
                stats["indexed"] += len(pending_texts)
                pending_texts.clear(); pending_records.clear()

            if progress_cb and idx % 100 == 0:
                progress_cb(idx / max(total, 1), stats)

        if pending_texts:
            vecs = await _embed_in_batches(pending_texts)
            store.add(vecs, pending_records)
            stats["indexed"] += len(pending_texts)

    store.save()
    if progress_cb:
        progress_cb(1.0, stats)
    return stats


async def index_profile(person_id: int) -> int:
    store = vector_store.profiles()
    store.delete_by_person(person_id)
    with get_session() as session:
        prof = session.get(InvestmentProfile, person_id)
        if not prof or not prof.ai_summary:
            return 0
        chunks = chunk_profile_summary(prof.ai_summary)
        if not chunks:
            return 0
        vecs = await gateway.embed(chunks)
        store.add(vecs, [{"text": c, "person_id": person_id, "metadata": {"kind": "profile_summary"}} for c in chunks])
        store.save()
        return len(chunks)
