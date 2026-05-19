from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import AppPaths, Settings


class AppState:
    paths: Optional[AppPaths] = None
    settings: Optional[Settings] = None

    @classmethod
    def init(cls, data_dir: Path) -> None:
        cls.paths = AppPaths(data_dir)
        cls.paths.ensure()
        cls.settings = Settings.load(cls.paths.config_file)
        if not cls.settings.data_dir:
            cls.settings.data_dir = str(data_dir)
            cls.settings.save(cls.paths.config_file)

    @classmethod
    def save_settings(cls) -> None:
        assert cls.paths and cls.settings
        cls.settings.save(cls.paths.config_file)


state = AppState
