from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    queries: list[str] = field(default_factory=lambda: ["electronics store lagos"])
    max_results_per_query: int = 50
    max_scrolls_per_query: int = 15
    max_runtime_seconds: int = 0
    output_dir: str = "csv_exports"
    logs_dir: str = "logs"
    checkpoint_dir: str = "checkpoints"
    archive_after_days: int = 14
    headless: bool = True
    enrich_websites: bool = True
    export_json: bool = True

    @classmethod
    def from_file(cls, path: str | None) -> "AppConfig":
        if not path:
            return cls()
        file_path = Path(path)
        if not file_path.exists():
            return cls()
        try:
            loaded = json.loads(file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        base = cls()
        for key, value in loaded.items():
            if hasattr(base, key):
                setattr(base, key, value)
        return base

