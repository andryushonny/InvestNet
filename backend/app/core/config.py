from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


def default_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "InvestNet"


class Models(BaseModel):
    embedding: str = "text-embedding-3-small"
    enrichment: str = "deepseek/deepseek-chat-v3.5:free"
    ranking: str = "deepseek/deepseek-chat-v3.5:free"
    composer: str = "deepseek/deepseek-chat-v3.5:free"


class ImportFilters(BaseModel):
    min_date: str | None = "2019-01-01"
    max_recipients: int = 5
    skip_sender_patterns: list[str] = Field(
        default_factory=lambda: [
            r"noreply@", r"no-reply@", r"donotreply@",
            r"notifications?@", r"alerts?@", r"updates?@",
            r"newsletter@", r"digest@", r"marketing@",
            r"@mailchimp", r"@sendgrid", r"@hubspot",
        ]
    )
    skip_subject_patterns: list[str] = Field(
        default_factory=lambda: [
            r"unsubscribe", r"newsletter", r"weekly digest",
            r"your receipt", r"order confirmation", r"shipping notification",
        ]
    )


class Settings(BaseModel):
    provider: Literal["openrouter", "openai"] = "openrouter"
    api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    embedding_provider: Literal["openrouter", "openai"] = "openai"
    embedding_api_key: str = ""
    models: Models = Field(default_factory=Models)
    filters: ImportFilters = Field(default_factory=ImportFilters)
    locale: Literal["ru", "en"] = "ru"
    data_dir: str = ""

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Settings":
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                return cls.model_validate(raw)
            except Exception:
                pass
        return cls()


class AppPaths:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.config_file = data_dir / "config.json"
        self.db_file = data_dir / "db.sqlite"
        self.vectors_dir = data_dir / "vectors"
        self.archives_dir = data_dir / "archives"
        self.logs_dir = data_dir / "logs"
        self.interactions_index = self.vectors_dir / "interactions.faiss"
        self.interactions_map = self.vectors_dir / "interactions.map.sqlite"
        self.profiles_index = self.vectors_dir / "profiles.faiss"
        self.profiles_map = self.vectors_dir / "profiles.map.sqlite"

    def ensure(self) -> None:
        for p in (self.data_dir, self.vectors_dir, self.archives_dir, self.logs_dir):
            p.mkdir(parents=True, exist_ok=True)
