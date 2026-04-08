"""FastAPI application main entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.api.routes import assessments, health, ai_routes
from src.bootstrap.config import get_settings

settings = get_settings()

_engine = None
_async_session_factory = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    global _engine, _async_session_factory
    _engine = create_async_engine(settings.database_url)
    _async_session_factory = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )
    yield
    if _engine:
        await _engine.dispose()


def get_db():
    """Dependency to get database session."""
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized")
    return _async_session_factory()


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
app.include_router(
    assessments.router, prefix=settings.api_v1_prefix, tags=["Assessments"]
)
app.include_router(ai_routes.router, prefix=settings.api_v1_prefix, tags=["AI"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MARS Noise Module API",
        "version": settings.app_version,
        "docs": "/docs",
    }
