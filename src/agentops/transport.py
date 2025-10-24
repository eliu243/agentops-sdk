from __future__ import annotations

import json
from typing import Any, Dict

import httpx

from .config import config


def post_event(event: Dict[str, Any]) -> None:
    try:
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        
        # Determine endpoint based on event type
        if event.get("type", "").startswith("a2a_"):
            url = f"{config.server_url}/v1/a2a-events"
        else:
            url = f"{config.server_url}/v1/events"
            
        with httpx.Client(timeout=3.0) as client:
            client.post(url, content=json.dumps(event), headers=headers)
    except Exception:
        pass


