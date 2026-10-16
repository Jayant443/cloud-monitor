import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from app.api.alerts import router as alerts_router
from app.api.api_keys import router as api_keys_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.readings import router as readings_router
from app.db import close_database, initialize_database
from app.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

def _docs_enabled() -> bool:
    return os.getenv("ENABLE_API_DOCS", "true").strip().casefold() in {
        "1", "true", "yes", "on",
    }

@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_database()
    evaluator_task: asyncio.Task | None = None
    try:
        from app.services.alert_evaluator import _enabled, alert_evaluator_loop

        if _enabled():
            evaluator_task = asyncio.create_task(alert_evaluator_loop())
    except Exception:
        logger.exception("could not start alert evaluator", extra={"event": "alert_evaluator_start_failed"})
    try:
        yield
    finally:
        if evaluator_task is not None:
            evaluator_task.cancel()
            try:
                await evaluator_task
            except asyncio.CancelledError:
                pass
        await close_database()

app = FastAPI(
    title="Cloud Monitoring API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled() else None,
    redoc_url="/redoc" if _docs_enabled() else None,
    openapi_url="/openapi.json" if _docs_enabled() else None,
)
cors_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "Authorization", "X-API-Key"],
)
app.include_router(metrics_router)
app.include_router(auth_router)
app.include_router(api_keys_router)
app.include_router(readings_router)
app.include_router(alerts_router)
app.include_router(health_router)

@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request failed",
            extra={
                "event": "http_request_failed",
                "method": request.method,
                "path": request.url.path,
            },
        )
        raise

    logger.info(
        "request completed",
        extra={
            "event": "http_request_completed",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    )
    return response

@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, exc: RequestValidationError,) -> JSONResponse:
    issues = [
        {
            "loc": list(error.get("loc", ())),
            "msg": error.get("msg", "Invalid request"),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]
    logger.warning(
        "request validation failed",
        extra={
            "event": "request_validation_failed",
            "method": request.method,
            "path": request.url.path,
            "status_code": 422,
        },
    )
    return JSONResponse(
        status_code=422,
        content={"detail": issues},
    )
