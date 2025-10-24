from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    server_url: str = "http://localhost:8000"
    api_key: Optional[str] = None
    project: str = "default"
    max_llm_calls: int = 5

    run_id: Optional[str] = None
    terminated: bool = False


config: Config = Config()


