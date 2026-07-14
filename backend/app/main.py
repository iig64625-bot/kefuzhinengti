"""StarSleep CS backend: API + SQLite sessions + logs + mock OMS HTTP tools."""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import RequestLog, SessionLocal, init_db
from .routers import chat, orders, tools, traces
from .schemas import HealthOut

app = FastAPI(
    title="StarSleep CS Backend",
    description=(
        "Thin owned backend for the portfolio Agent: chat sessions, SQLite persistence, "
        "request logs, traces, tickets, and HTTP mock OMS with timeout/retry degradation."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    t0 = time.perf_counter()
    response: Response = await call_next(request)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Latency-Ms"] = str(latency_ms)

    # Persist access log (skip docs noise lightly)
    if not request.url.path.startswith("/docs") and request.url.path != "/openapi.json":
        db = SessionLocal()
        try:
            db.add(
                RequestLog(
                    request_id=request_id,
                    method=request.method,
                    path=str(request.url.path),
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                    client_ip=request.client.host if request.client else None,
                )
            )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        finally:
            db.close()
    return response


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health", response_model=HealthOut)
def health():
    settings = get_settings()
    return HealthOut(
        status="ok",
        service="starsleep-cs-backend",
        public_base_url=settings.public_base_url,
        dify_configured=bool(settings.dify_api_key),
    )


app.include_router(chat.router)
app.include_router(orders.router)
app.include_router(tools.router)
app.include_router(traces.router)
