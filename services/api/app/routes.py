from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Event, Run, A2AEvent
from .schemas import EventIn, A2AEventIn, RunDetail, RunSummary


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/v1/events")
def ingest_event(payload: EventIn, db: Session = Depends(get_db)) -> dict:
    if payload.type == "run_started":
        run = db.get(Run, payload.run_id)
        if run is None:
            run = Run(
                id=payload.run_id,
                project=payload.project or "default",
                started_at=payload.started_at or 0,
                status="running",
            )
            db.add(run)
            db.commit()
        return {"ok": True}

    run = db.get(Run, payload.run_id)
    if run is None:
        raise HTTPException(status_code=400, detail="run_id not found; send run_started first")

    if payload.type == "llm_call":
        evt = Event(
            run_id=payload.run_id,
            seq=payload.seq,
            type="llm_call",
            model=payload.model,
            prompt=payload.prompt,
            response=payload.response,
            prompt_tokens=payload.prompt_tokens,
            completion_tokens=payload.completion_tokens,
            total_tokens=payload.total_tokens,
            cost_usd=payload.cost_usd,
            created_at=payload.created_at,
        )
        db.add(evt)
        db.commit()
        return {"ok": True}

    if payload.type == "run_terminated":
        run.status = "terminated"
        run.termination_reason = payload.reason
        run.ended_at = payload.terminated_at
        db.add(run)
        db.commit()
        return {"ok": True}

    if payload.type == "run_completed":
        run.status = "completed"
        run.ended_at = payload.ended_at
        db.add(run)
        db.commit()
        return {"ok": True}

    raise HTTPException(status_code=400, detail="unknown event type")


@router.post("/v1/a2a-events")
def ingest_a2a_event(payload: A2AEventIn, db: Session = Depends(get_db)) -> dict:
    """Ingest A2A communication events."""
    # Verify run exists
    run = db.get(Run, payload.run_id)
    if run is None:
        raise HTTPException(status_code=400, detail="run_id not found")
    
    # Create A2A event
    a2a_event = A2AEvent(
        run_id=payload.run_id,
        type=payload.type,
        method=payload.method,
        url=payload.url,
        service_name=payload.service_name,
        request_data=payload.request_data,
        response_data=payload.response_data,
        status_code=payload.status_code,
        duration_ms=payload.duration_ms,
        error=payload.error,
        created_at=payload.created_at,
    )
    
    db.add(a2a_event)
    db.commit()
    
    return {"ok": True}


@router.get("/v1/runs", response_model=List[RunSummary])
def list_runs(
    db: Session = Depends(get_db),
    project: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    q = db.query(Run)
    if project:
        q = q.filter(Run.project == project)
    q = q.order_by(Run.started_at.desc()).limit(limit)
    runs: List[Run] = q.all()

    # Aggregate costs per run
    result: List[RunSummary] = []
    for r in runs:
        total_cost = (
            db.query(func.coalesce(func.sum(Event.cost_usd), 0.0))
            .filter(Event.run_id == r.id)
            .scalar()
            or 0.0
        )
        result.append(
            RunSummary(
                id=r.id,
                project=r.project,
                started_at=r.started_at,
                ended_at=r.ended_at,
                status=r.status,
                termination_reason=r.termination_reason,
                total_cost_usd=float(total_cost),
            )
        )
    return result


@router.get("/v1/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    # Get both regular events and A2A events
    events = (
        db.query(Event)
        .filter(Event.run_id == run_id)
        .order_by(Event.id.asc())
        .all()
    )
    
    a2a_events = (
        db.query(A2AEvent)
        .filter(A2AEvent.run_id == run_id)
        .order_by(A2AEvent.id.asc())
        .all()
    )

    total_cost = (
        db.query(func.coalesce(func.sum(Event.cost_usd), 0.0))
        .filter(Event.run_id == run_id)
        .scalar()
        or 0.0
    )

    return RunDetail(
        id=run.id,
        project=run.project,
        started_at=run.started_at,
        ended_at=run.ended_at,
        status=run.status,
        termination_reason=run.termination_reason,
        total_cost_usd=float(total_cost),
        events=[
            {
                "id": e.id,
                "type": e.type,
                "model": e.model,
                "prompt": e.prompt,
                "response": e.response,
                "prompt_tokens": e.prompt_tokens,
                "completion_tokens": e.completion_tokens,
                "total_tokens": e.total_tokens,
                "cost_usd": e.cost_usd,
                "created_at": e.created_at,
            }
            for e in events
        ] + [
            {
                "id": f"a2a_{ae.id}",
                "type": ae.type,
                "method": ae.method,
                "url": ae.url,
                "service_name": ae.service_name,
                "request_data": ae.request_data,
                "response_data": ae.response_data,
                "status_code": ae.status_code,
                "duration_ms": ae.duration_ms,
                "error": ae.error,
                "created_at": ae.created_at,
            }
            for ae in a2a_events
        ],
    )


@router.delete("/v1/runs/{run_id}")
def delete_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    """Delete a run and all its associated events."""
    # Check if run exists
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    
    # Delete the run (cascade will handle events and A2A events)
    db.delete(run)
    db.commit()
    
    return {"ok": True, "message": f"Run {run_id} deleted successfully"}


