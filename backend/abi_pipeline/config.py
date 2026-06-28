from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    api_base_url: str = os.getenv("ABI_API_BASE_URL", "https://hackathon.prod.pulsefoundry.ai")
    db_path: Path = Path(os.getenv("ABI_DB_PATH", "abi_pipeline.db"))
    worker_count: int = int(os.getenv("ABI_WORKERS", "30"))
    max_attempts: int = int(os.getenv("ABI_MAX_ATTEMPTS", "8"))
    request_timeout_seconds: int = int(os.getenv("ABI_REQUEST_TIMEOUT_SECONDS", "30"))
    facilities: tuple[int, ...] = (101, 102, 103)


settings = Settings()
