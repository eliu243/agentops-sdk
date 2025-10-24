from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from .db import Base


class Run(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True, index=True)
    project = Column(String, index=True, nullable=False)
    started_at = Column(Integer, nullable=False)  # epoch ms
    ended_at = Column(Integer, nullable=True)  # epoch ms
    status = Column(String, nullable=False, default="running")  # running|completed|terminated
    termination_reason = Column(String, nullable=True)

    events = relationship("Event", back_populates="run", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    seq = Column(Integer, nullable=True)
    type = Column(String, nullable=False)
    model = Column(String, nullable=True)
    prompt = Column(Text, nullable=True)
    response = Column(Text, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    created_at = Column(Integer, nullable=True)

    run = relationship("Run", back_populates="events")


class A2AEvent(Base):
    __tablename__ = "a2a_events"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    type = Column(String, nullable=False)  # a2a_http_call, a2a_db_query, etc.
    method = Column(String, nullable=True)  # GET, POST, etc.
    url = Column(Text, nullable=True)  # Full URL
    service_name = Column(String, nullable=True)  # Clean service name
    request_data = Column(Text, nullable=True)  # Request payload
    response_data = Column(Text, nullable=True)  # Response payload
    status_code = Column(Integer, nullable=True)  # HTTP status code
    duration_ms = Column(Float, nullable=True)  # Request duration
    error = Column(Text, nullable=True)  # Error message if failed
    created_at = Column(Integer, nullable=True)  # Epoch milliseconds

    run = relationship("Run")


