from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Awaitable, Callable

from loguru import logger
from sqlmodel import select

from ..db.models import BackgroundTask
from ..db.session import get_session


_running: dict[int, asyncio.Task] = {}
_subscribers: dict[int, list[asyncio.Queue]] = {}


def create_task(kind: str) -> int:
    with get_session() as session:
        bt = BackgroundTask(kind=kind, status="queued")
        session.add(bt)
        session.commit()
        session.refresh(bt)
        return bt.id


def update_task(task_id: int, **fields) -> None:
    with get_session() as session:
        bt = session.get(BackgroundTask, task_id)
        if not bt:
            return
        for k, v in fields.items():
            setattr(bt, k, v)
        session.add(bt)
        session.commit()


def get_task(task_id: int) -> dict | None:
    with get_session() as session:
        bt = session.get(BackgroundTask, task_id)
        if not bt:
            return None
        return bt.model_dump()


def list_tasks(limit: int = 50) -> list[dict]:
    with get_session() as session:
        rows = session.exec(select(BackgroundTask).order_by(BackgroundTask.id.desc())).all()[:limit]
        return [r.model_dump() for r in rows]


def _publish(task_id: int, event: dict) -> None:
    for q in _subscribers.get(task_id, []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


def subscribe(task_id: int) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subscribers.setdefault(task_id, []).append(q)
    return q


def unsubscribe(task_id: int, q: asyncio.Queue) -> None:
    subs = _subscribers.get(task_id)
    if subs and q in subs:
        subs.remove(q)


def run_async(kind: str, coro_factory: Callable[[Callable[[float, Any], None]], Awaitable[Any]]) -> int:
    """Launch async task with progress callback. Returns task id."""
    task_id = create_task(kind)

    def progress(p: float, msg: Any = None):
        update_task(task_id, progress=float(p), message=json.dumps(msg, ensure_ascii=False, default=str) if msg else None)
        _publish(task_id, {"progress": p, "message": msg})

    async def runner():
        update_task(task_id, status="running", started_at=datetime.utcnow())
        try:
            result = await coro_factory(progress)
            update_task(
                task_id,
                status="done",
                progress=1.0,
                finished_at=datetime.utcnow(),
                message=json.dumps(result, ensure_ascii=False, default=str) if result is not None else None,
            )
            _publish(task_id, {"done": True, "result": result})
        except Exception as e:
            logger.exception(f"task {kind} failed")
            update_task(task_id, status="failed", finished_at=datetime.utcnow(), error=str(e))
            _publish(task_id, {"failed": True, "error": str(e)})
        finally:
            _running.pop(task_id, None)

    _running[task_id] = asyncio.create_task(runner())
    return task_id
