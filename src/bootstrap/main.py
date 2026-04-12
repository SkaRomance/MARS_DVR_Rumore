"""FastAPI application main entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import (
    auth_routes,
    assessments,
    health,
    ai_routes,
    export_routes,
    license_routes,
    admin_routes,
    ateco_routes,
    rag_routes,
)
from src.bootstrap.config import get_settings
from src.bootstrap.database import get_engine, dispose_engine, init_db
from src.infrastructure.middleware.rate_limiter import (
    init_rate_limiter,
    close_rate_limiter,
)
from src.infrastructure.middleware.audit import AuditMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    await init_db()
    await init_rate_limiter()
    yield
    await close_rate_limiter()
    await dispose_engine()


app = FastAPI(
    title="MARS Noise Module API",
    description="Modulo DVR Rischio Rumore per consulenti HSE - D.Lgs. 81/2008",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

static_path = Path(__file__).parent.parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(auth_routes.router, prefix=settings.api_v1_prefix, tags=["Auth"])
app.include_router(export_routes.router, prefix=settings.api_v1_prefix, tags=["Export"])
app.include_router(
    assessments.router, prefix=settings.api_v1_prefix, tags=["Assessments"]
)
app.include_router(ai_routes.router, prefix=settings.api_v1_prefix, tags=["AI"])
app.include_router(
    license_routes.router, prefix=settings.api_v1_prefix, tags=["License"]
)
app.include_router(admin_routes.router, prefix=settings.api_v1_prefix, tags=["Admin"])
app.include_router(ateco_routes.router, prefix=settings.api_v1_prefix, tags=["ATECO"])
app.include_router(
    rag_routes.router, prefix=settings.api_v1_prefix + "/rag", tags=["RAG"]
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MARS Noise Module API",
        "version": settings.app_version,
        "docs": "/docs",
    }
