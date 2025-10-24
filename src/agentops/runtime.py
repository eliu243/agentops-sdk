from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

from .config import config
from .transport import post_event


_local = threading.local()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _get_seq_counter() -> int:
    if not hasattr(_local, "seq"):
        _local.seq = 0
    return _local.seq


def next_sequence() -> int:
    seq = _get_seq_counter() + 1
    _local.seq = seq
    return seq


def current_run_id() -> Optional[str]:
    return getattr(_local, "run_id", None) or config.run_id


def _set_run_id(run_id: str) -> None:
    _local.run_id = run_id
    config.run_id = run_id


@contextmanager
def RunContext(project: Optional[str] = None) -> Iterator[str]:
    run_id = str(uuid.uuid4())
    _set_run_id(run_id)
    post_event(
        {
            "type": "run_started",
            "run_id": run_id,
            "project": project or config.project,
            "started_at": _now_ms(),
        }
    )
    try:
        yield run_id
    finally:
        post_event({"type": "run_completed", "run_id": run_id, "ended_at": _now_ms()})
        _local.seq = 0
        _local.run_id = None


def ensure_run_started() -> str:
    rid = current_run_id()
    if rid:
        return rid
    rid = str(uuid.uuid4())
    _set_run_id(rid)
    post_event(
        {
            "type": "run_started",
            "run_id": rid,
            "project": config.project,
            "started_at": _now_ms(),
        }
    )
    return rid


