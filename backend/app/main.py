from __future__ import annotations

import argparse
import socket
import sys
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .api.routes import router
from .core.config import default_data_dir
from .core.state import state
from .db.session import init_db
from .indexing import vector_store


def create_app(data_dir: Path) -> FastAPI:
    state.init(data_dir)
    paths = state.paths
    assert paths

    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(paths.logs_dir / "backend.log", level="DEBUG", rotation="10 MB", retention=3)

    init_db(paths.db_file)
    vector_store.init_stores(
        paths.interactions_index,
        paths.interactions_map,
        paths.profiles_index,
        paths.profiles_map,
    )

    app = FastAPI(title="InvestNet", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api/v1")

    @app.on_event("shutdown")
    def _save():
        try:
            vector_store.save_all()
        except Exception:
            logger.exception("save vector stores")

    return app


def pick_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def write_port_file(port: int) -> None:
    p = Path(tempfile.gettempdir()) / "investnet.port"
    p.write_text(str(port), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--data-dir", type=str, default="")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else default_data_dir()
    port = args.port or pick_free_port()
    write_port_file(port)

    app = create_app(data_dir)
    logger.info(f"InvestNet backend on http://{args.host}:{port} (data: {data_dir})")
    uvicorn.run(app, host=args.host, port=port, log_level="info")


if __name__ == "__main__":
    main()
