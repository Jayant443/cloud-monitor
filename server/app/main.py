import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.db import close_database, initialize_database
from app.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_database()
    yield
    await close_database()

app = FastAPI(title="Cloud Monitoring API", version="1.0.0", lifespan=lifespan)
app.include_router(metrics_router)
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
