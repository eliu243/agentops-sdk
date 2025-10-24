from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    type: Literal["run_started", "llm_call", "run_terminated", "run_completed"]
    run_id: str
    project: Optional[str] = None
    started_at: Optional[int] = None
    ended_at: Optional[int] = None
    terminated_at: Optional[int] = None

    # llm fields
    seq: Optional[int] = None
    model: Optional[str] = None
    prompt: Optional[str] = None
    response: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    created_at: Optional[int] = None

    # guardrail
    reason: Optional[str] = None


class A2AEventIn(BaseModel):
    run_id: str
    type: str  # a2a_http_call, a2a_db_query, etc.
    method: Optional[str] = None
    url: Optional[str] = None
    service_name: Optional[str] = None
    request_data: Optional[str] = None
    response_data: Optional[str] = None
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    created_at: Optional[int] = None


class RunSummary(BaseModel):
    id: str
    project: str
    started_at: int
    ended_at: Optional[int]
    status: str
    termination_reason: Optional[str]
    total_cost_usd: float = 0.0


class RunDetail(RunSummary):
    events: list[dict]


