"""FastAPI entrypoint. Run: uvicorn app.main:app --host 127.0.0.1 --port 8321"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import analysis, core, integrations, labs
from app.core.config import settings

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # sandbox preview gateway; restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(core.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(integrations.ads_router, prefix="/api/v1")
app.include_router(integrations.yt_router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(labs.router, prefix="/api/v1")


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=422,
                        content={"error": {"code": "validation_error", "message": str(exc)}})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500,
                        content={"error": {"code": "internal_error",
                                           "message": f"{type(exc).__name__}: {exc}"[:400]}})


@app.on_event("startup")
def on_startup() -> None:
    from app.core.db import init_db

    init_db()


@app.get("/")
def root():
    return {"app": settings.APP_NAME, "docs": "/api/docs",
            "health": "/api/v1/health"}
