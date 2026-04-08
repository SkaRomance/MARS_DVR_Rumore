"""FastAPI application main entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import assessments, health
from src.bootstrap.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    yield
    # Shutdown
    pass


app = FastAPI(
    title="MARS Noise Module API",
    description="Modulo DVR Rischio Rumore per consulenti HSE - D.Lgs. 81/2008",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(assessments.router, prefix=settings.api_v1_prefix, tags=["Assessments"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"name": "MARS Noise Module API", "version": settings.app_version, "docs": "/docs"}
