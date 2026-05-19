from __future__ import annotations

import asyncio
import json
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import select, or_
from sse_starlette.sse import EventSourceResponse

from ..composer.composer import compose_for_deal
from ..core.state import state
from ..db.models import (
    BackgroundTask,
    Deal,
    GeneratedEmailDraft,
    Interaction,
    InvestmentCase,
    InvestmentProfile,
    Person,
)
from ..db.session import get_session
from ..enrichment.enricher import enrich_batch, enrich_person
from ..importers.gmail import import_mbox
from ..importers.linkedin import import_linkedin_zip
from ..indexing.indexer import index_interactions, index_profile
from ..ranking.ranker import rank_case
from . import tasks

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "ts": datetime.utcnow().isoformat()}


# ---------- Settings ----------

class SettingsUpdate(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_api_key: Optional[str] = None
    models: Optional[dict] = None
    filters: Optional[dict] = None
    locale: Optional[str] = None
    self_emails: Optional[list[str]] = None


@router.get("/settings")
def get_settings() -> dict:
    s = state.settings
    if not s:
        raise HTTPException(500, "not initialised")
    d = s.model_dump()
    if d.get("api_key"):
        d["api_key_masked"] = d["api_key"][:4] + "..." + d["api_key"][-4:] if len(d["api_key"]) > 8 else "***"
    if d.get("embedding_api_key"):
        d["embedding_api_key_masked"] = "***"
    self_file = Path(s.data_dir) / "self_emails.json"
    d["self_emails"] = json.loads(self_file.read_text(encoding="utf-8")) if self_file.exists() else []
    d["api_key"] = ""
    d["embedding_api_key"] = ""
    return d


@router.put("/settings")
def update_settings(payload: SettingsUpdate) -> dict:
    s = state.settings
    if not s:
        raise HTTPException(500, "not initialised")
    data = payload.model_dump(exclude_none=True)
    self_emails = data.pop("self_emails", None)
    if "models" in data:
        for k, v in data["models"].items():
            setattr(s.models, k, v)
        data.pop("models")
    if "filters" in data:
        for k, v in data["filters"].items():
            setattr(s.filters, k, v)
        data.pop("filters")
    for k, v in data.items():
        setattr(s, k, v)
    state.save_settings()
    if self_emails is not None:
        self_file = Path(s.data_dir) / "self_emails.json"
        self_file.write_text(json.dumps(self_emails), encoding="utf-8")
    return get_settings()


# ---------- Imports ----------

class ImportRequest(BaseModel):
    path: str


@router.post("/import/gmail")
def import_gmail(req: ImportRequest) -> dict:
    src = Path(req.path)
    if not src.exists():
        raise HTTPException(404, f"file not found: {src}")
    paths = state.paths
    assert paths
    dest = paths.archives_dir / "gmail-takeout.mbox"
    if str(src.resolve()) != str(dest.resolve()):
        shutil.copy2(src, dest)

    def coro_factory(progress):
        async def go():
            def cb(p, st):
                progress(p, st)
            stats = await asyncio.to_thread(import_mbox, dest, cb)
            return stats
        return go()

    tid = tasks.run_async("import_gmail", coro_factory)
    return {"task_id": tid}


@router.post("/import/linkedin")
def import_linkedin(req: ImportRequest) -> dict:
    src = Path(req.path)
    if not src.exists():
        raise HTTPException(404, f"file not found: {src}")
    paths = state.paths
    assert paths
    dest = paths.archives_dir / "linkedin-export.zip"
    if str(src.resolve()) != str(dest.resolve()):
        shutil.copy2(src, dest)

    def coro_factory(progress):
        async def go():
            def cb(p, st):
                progress(p, st)
            stats = await asyncio.to_thread(import_linkedin_zip, dest, cb)
            return stats
        return go()

    tid = tasks.run_async("import_linkedin", coro_factory)
    return {"task_id": tid}


@router.post("/index/reindex")
def reindex() -> dict:
    def coro_factory(progress):
        return index_interactions(progress)
    tid = tasks.run_async("reindex_interactions", coro_factory)
    return {"task_id": tid}


# ---------- Tasks ----------

@router.get("/tasks")
def get_tasks(limit: int = 50) -> list[dict]:
    return tasks.list_tasks(limit)


@router.get("/tasks/{task_id}")
def get_task(task_id: int) -> dict:
    t = tasks.get_task(task_id)
    if not t:
        raise HTTPException(404, "task not found")
    return t


@router.get("/tasks/{task_id}/stream")
async def stream_task(task_id: int):
    q = tasks.subscribe(task_id)

    async def gen():
        try:
            current = tasks.get_task(task_id)
            if current:
                yield {"event": "snapshot", "data": json.dumps(current, default=str)}
                if current["status"] in ("done", "failed"):
                    return
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield {"event": "update", "data": json.dumps(ev, default=str)}
                    if ev.get("done") or ev.get("failed"):
                        return
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            tasks.unsubscribe(task_id, q)

    return EventSourceResponse(gen())


# ---------- Persons ----------

@router.get("/persons")
def list_persons(
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    enriched: Optional[bool] = None,
) -> dict:
    with get_session() as session:
        stmt = select(Person)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Person.full_name.like(like), Person.primary_email.like(like), Person.company.like(like)))
        rows = session.exec(stmt.order_by(Person.id.desc())).all()
        total = len(rows)
        page = rows[offset:offset + limit]
        out = []
        for p in page:
            prof = session.get(InvestmentProfile, p.id)
            d = p.model_dump()
            d["has_profile"] = bool(prof and prof.ai_summary)
            d["confidence"] = prof.confidence if prof else None
            count = session.exec(
                select(func.count()).select_from(Interaction).where(Interaction.person_id == p.id)
            ).one()
            d["interactions_count"] = int(count) if not isinstance(count, tuple) else int(count[0])
            out.append(d)
        if enriched is True:
            out = [o for o in out if o["has_profile"]]
        elif enriched is False:
            out = [o for o in out if not o["has_profile"]]
        return {"total": total, "items": out}


@router.get("/persons/{person_id}")
def get_person(person_id: int) -> dict:
    with get_session() as session:
        p = session.get(Person, person_id)
        if not p:
            raise HTTPException(404)
        prof = session.get(InvestmentProfile, person_id)
        ias = session.exec(
            select(Interaction).where(Interaction.person_id == person_id).order_by(Interaction.occurred_at.desc())
        ).all()
        deals = session.exec(select(Deal).where(Deal.person_id == person_id)).all()
        drafts = []
        for d in deals:
            ds = session.exec(select(GeneratedEmailDraft).where(GeneratedEmailDraft.deal_id == d.id)).all()
            drafts.extend([x.model_dump() for x in ds])
        return {
            "person": p.model_dump(),
            "profile": prof.model_dump() if prof else None,
            "interactions": [i.model_dump() for i in ias[:200]],
            "deals": [d.model_dump() for d in deals],
            "drafts": drafts,
        }


@router.post("/persons/{person_id}/enrich")
def enrich_one(person_id: int) -> dict:
    def coro_factory(progress):
        async def go():
            r = await enrich_person(person_id)
            return {"enriched": bool(r)}
        return go()
    tid = tasks.run_async("enrich_person", coro_factory)
    return {"task_id": tid}


class BatchEnrichRequest(BaseModel):
    person_ids: list[int]


@router.post("/persons/enrich-batch")
def enrich_many(req: BatchEnrichRequest) -> dict:
    if not req.person_ids:
        raise HTTPException(400, "person_ids required")

    def coro_factory(progress):
        async def go():
            return await enrich_batch(req.person_ids, progress)
        return go()
    tid = tasks.run_async("enrich_batch", coro_factory)
    return {"task_id": tid}


# ---------- Cases ----------

class CaseCreate(BaseModel):
    title: str
    description: str
    stage: Optional[str] = None
    geography: Optional[str] = None
    sector: Optional[str] = None
    ticket_range: Optional[str] = None


@router.post("/cases")
def create_case(payload: CaseCreate) -> dict:
    with get_session() as session:
        c = InvestmentCase(**payload.model_dump())
        session.add(c)
        session.commit()
        session.refresh(c)
        return c.model_dump()


@router.get("/cases")
def list_cases() -> list[dict]:
    with get_session() as session:
        rows = session.exec(select(InvestmentCase).order_by(InvestmentCase.id.desc())).all()
        return [r.model_dump() for r in rows]


@router.get("/cases/{case_id}")
def get_case(case_id: int) -> dict:
    with get_session() as session:
        c = session.get(InvestmentCase, case_id)
        if not c:
            raise HTTPException(404)
        return c.model_dump()


@router.delete("/cases/{case_id}")
def delete_case(case_id: int) -> dict:
    with get_session() as session:
        c = session.get(InvestmentCase, case_id)
        if not c:
            raise HTTPException(404)
        session.delete(c)
        session.commit()
        return {"ok": True}


@router.post("/cases/{case_id}/rank")
def trigger_rank(case_id: int, top_n: int = 100) -> dict:
    def coro_factory(progress):
        async def go():
            return await rank_case(case_id, top_n_candidates=top_n, progress_cb=progress)
        return go()
    tid = tasks.run_async("rank_case", coro_factory)
    return {"task_id": tid}


@router.get("/cases/{case_id}/deals")
def case_deals(case_id: int) -> list[dict]:
    with get_session() as session:
        rows = session.exec(
            select(Deal).where(Deal.case_id == case_id).order_by(Deal.score.desc())
        ).all()
        out = []
        for d in rows:
            person = session.get(Person, d.person_id)
            prof = session.get(InvestmentProfile, d.person_id)
            dd = d.model_dump()
            dd["person"] = person.model_dump() if person else None
            dd["profile_summary"] = prof.ai_summary if prof else None
            if d.reasoning:
                try:
                    dd["reasoning_json"] = json.loads(d.reasoning)
                except Exception:
                    dd["reasoning_json"] = None
            out.append(dd)
        return out


# ---------- Deals ----------

class DealUpdate(BaseModel):
    status: Optional[str] = None
    next_action: Optional[str] = None


@router.patch("/deals/{deal_id}")
def update_deal(deal_id: int, payload: DealUpdate) -> dict:
    with get_session() as session:
        d = session.get(Deal, deal_id)
        if not d:
            raise HTTPException(404)
        if payload.status:
            d.status = payload.status
        if payload.next_action is not None:
            d.next_action = payload.next_action
        d.updated_at = datetime.utcnow()
        session.add(d)
        session.commit()
        session.refresh(d)
        return d.model_dump()


@router.post("/deals/{deal_id}/draft-email")
def draft_email(deal_id: int) -> dict:
    def coro_factory(progress):
        async def go():
            draft = await compose_for_deal(deal_id)
            return draft.model_dump() if draft else None
        return go()
    tid = tasks.run_async("compose_email", coro_factory)
    return {"task_id": tid}


@router.get("/deals/{deal_id}/drafts")
def list_drafts(deal_id: int) -> list[dict]:
    with get_session() as session:
        rows = session.exec(
            select(GeneratedEmailDraft).where(GeneratedEmailDraft.deal_id == deal_id).order_by(GeneratedEmailDraft.id.desc())
        ).all()
        return [r.model_dump() for r in rows]


class DraftUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    user_sent: Optional[int] = None


@router.patch("/drafts/{draft_id}")
def update_draft(draft_id: int, payload: DraftUpdate) -> dict:
    with get_session() as session:
        d = session.get(GeneratedEmailDraft, draft_id)
        if not d:
            raise HTTPException(404)
        if payload.subject is not None and payload.subject != d.subject:
            d.subject = payload.subject; d.user_edited = 1
        if payload.body is not None and payload.body != d.body:
            d.body = payload.body; d.user_edited = 1
        if payload.user_sent is not None:
            d.user_sent = int(payload.user_sent)
        session.add(d)
        session.commit()
        session.refresh(d)
        return d.model_dump()


# ---------- Dashboard ----------

@router.get("/dashboard")
def dashboard() -> dict:
    def _count(stmt):
        v = session.exec(stmt).one()
        return int(v[0] if isinstance(v, tuple) else v)
    with get_session() as session:
        persons = _count(select(func.count()).select_from(Person))
        cases = _count(select(func.count()).select_from(InvestmentCase))
        open_deals = _count(select(func.count()).select_from(Deal).where(Deal.status.not_in(["won", "lost"])))
        enriched = _count(select(func.count()).select_from(InvestmentProfile))
        interactions_total = _count(select(func.count()).select_from(Interaction))
    return {
        "persons": persons,
        "cases": cases,
        "open_deals": open_deals,
        "enriched": enriched,
        "interactions": interactions_total,
    }
