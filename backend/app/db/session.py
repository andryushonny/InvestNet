from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from . import models  # noqa: F401  -- needed for metadata registration

_engine: Engine | None = None


def init_db(db_file: Path) -> Engine:
    global _engine
    db_file.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{db_file.as_posix()}"
    _engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})

    @event.listens_for(_engine, "connect")
    def _pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA cache_size=-64000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    SQLModel.metadata.create_all(_engine)
    return _engine


def engine() -> Engine:
    assert _engine is not None, "DB not initialised"
    return _engine


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(engine()) as s:
        yield s
