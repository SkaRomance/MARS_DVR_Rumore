"""FastAPI application main entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import (
    admin_routes,
    ai_routes,
    assessments,
    ateco_routes,
    auth_routes,
    catalog_routes,
    company_routes,
    context_routes,
    export_routes,
    health,
    job_role_routes,
    license_routes,
    machine_asset_routes,
    mitigation_routes,
    rag_routes,
)
from src.bootstrap.config import get_settings
from src.bootstrap.database import dispose_engine, init_db
from src.infrastructure.middleware.audit import AuditMiddleware
from src.infrastructure.middleware.rate_limiter import (
    close_rate_limiter,
    init_rate_limiter,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    settings = get_settings()
    if settings.app_env != "development" and (
        not settings.jwt_secret_key or settings.jwt_secret_key == "change-me-in-production"
    ):
        raise RuntimeError("JWT_SECRET_KEY must be set in production")
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
    allow_headers=settings.cors_headers,
)

static_path = Path(__file__).parent.parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(auth_routes.router, prefix=settings.api_v1_prefix, tags=["Auth"])
app.include_router(export_routes.router, prefix=settings.api_v1_prefix, tags=["Export"])
app.include_router(assessments.router, prefix=settings.api_v1_prefix, tags=["Assessments"])
app.include_router(ai_routes.router, prefix=settings.api_v1_prefix, tags=["AI"])
app.include_router(license_routes.router, prefix=settings.api_v1_prefix, tags=["License"])
app.include_router(admin_routes.router, prefix=settings.api_v1_prefix, tags=["Admin"])
app.include_router(ateco_routes.router, prefix=settings.api_v1_prefix, tags=["ATECO"])
app.include_router(
    company_routes.router,
    prefix=settings.api_v1_prefix + "/companies",
    tags=["Companies"],
)
app.include_router(
    job_role_routes.router,
    prefix=settings.api_v1_prefix + "/job-roles",
    tags=["Job Roles"],
)
app.include_router(
    mitigation_routes.router,
    prefix=settings.api_v1_prefix + "/mitigations",
    tags=["Mitigations"],
)
app.include_router(
    machine_asset_routes.router,
    prefix=settings.api_v1_prefix + "/machine-assets",
    tags=["Machine Assets"],
)
app.include_router(
    catalog_routes.router,
    prefix=settings.api_v1_prefix + "/catalog",
    tags=["Noise Source Catalog"],
)
app.include_router(rag_routes.router, prefix=settings.api_v1_prefix + "/rag", tags=["RAG"])
app.include_router(context_routes.router, prefix=settings.api_v1_prefix, tags=["Noise Contexts"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MARS Noise Module API",
        "version": settings.app_version,
        "docs": "/docs",
    }
