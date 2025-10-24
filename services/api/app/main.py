from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from .models import Event, Run
from .routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="AgentOps API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create tables on startup
    Base.metadata.create_all(bind=engine)

    app.include_router(router)
    return app


app = create_app()


