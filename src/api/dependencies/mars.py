"""FastAPI dependencies for MARS-authenticated requests.

The `require_mars_context` dependency reads the Authorization header,
validates the JWT against MARS (RS256+JWKS or HS256), resolves the
tenant context, and returns a `MarsContext` to route handlers.

Singletons (MarsApiClient, MarsJwtValidator, TenantResolver) are
created on first access and stored on `app.state` so they survive
across requests and are closed cleanly during shutdown.

For tests or alternate deployments, overrides can swap any of these
via FastAPI's `app.dependency_overrides`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.bootstrap.config import get_settings
from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.exceptions import (
    MarsApiError,
    MarsAuthError,
    MarsPaymentRequiredError,
)
from src.infrastructure.mars.jwt_validator import MarsJwtValidator
from src.infrastructure.mars.tenant_resolver import AsyncCache, TenantResolver
from src.infrastructure.mars.types import MarsContext

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


# ── singleton factories ────────────────────────────────────────────
#
# These build one instance per process. In production the FastAPI app
# stores them on `app.state` during lifespan startup so they share
# their underlying httpx client / Redis pool across requests.
# For unit tests that don't run a full app, the lru_cache lets you
# build throwaway instances — just call `reset_mars_singletons()`
# between tests to avoid leaking state.


@lru_cache(maxsize=1)
def _cached_mars_client() -> MarsApiClient:
    settings = get_settings()
    return MarsApiClient(
        base_url=settings.mars_api_base_url,
        timeout=settings.mars_http_timeout_seconds,
        max_retries=settings.mars_http_max_retries,
    )


@lru_cache(maxsize=1)
def _cached_jwt_validator() -> MarsJwtValidator:
    settings = get_settings()
    return MarsJwtValidator(
        algorithm=settings.mars_jwt_algorithm,
        issuer=settings.mars_issuer,
        audience=settings.mars_audience,
        jwks_url=settings.mars_jwks_url or None,
        hs256_secret=settings.mars_jwt_hs256_secret or None,
        jwks_cache_ttl=settings.mars_jwks_cache_ttl_seconds,
    )


def reset_mars_singletons() -> None:
    """Clear cached singletons. Use in tests between scenarios."""
    _cached_mars_client.cache_clear()
    _cached_jwt_validator.cache_clear()


# ── FastAPI dependency functions ───────────────────────────────────


def get_mars_client(request: Request) -> MarsApiClient:
    """Provide the per-app MarsApiClient singleton."""
    client = getattr(request.app.state, "mars_client", None)
    if client is None:
        client = _cached_mars_client()
        request.app.state.mars_client = client
    return client


def get_mars_jwt_validator(request: Request) -> MarsJwtValidator:
    """Provide the per-app MarsJwtValidator singleton."""
    validator = getattr(request.app.state, "mars_jwt_validator", None)
    if validator is None:
        validator = _cached_jwt_validator()
        request.app.state.mars_jwt_validator = validator
    return validator


def get_mars_cache(request: Request) -> AsyncCache | None:
    """Provide a cache layer for the tenant resolver.

    If the app has no Redis wired up (dev without cache), returns None
    and TenantResolver falls back to network-only path.
    """
    return getattr(request.app.state, "mars_cache", None)


def get_mars_tenant_resolver(
    request: Request,
    client: MarsApiClient = Depends(get_mars_client),
    cache: AsyncCache | None = Depends(get_mars_cache),
) -> TenantResolver:
    """Provide the per-app TenantResolver, building one if needed."""
    resolver = getattr(request.app.state, "mars_tenant_resolver", None)
    if resolver is None:
        settings = get_settings()
        resolver = TenantResolver(
            cache=cache,
            mars_client=client,
            cache_ttl_seconds=settings.mars_tenant_cache_ttl_seconds,
        )
        request.app.state.mars_tenant_resolver = resolver
    return resolver


# ── main auth dependency ───────────────────────────────────────────


async def require_mars_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    validator: Annotated[MarsJwtValidator, Depends(get_mars_jwt_validator)],
    resolver: Annotated[TenantResolver, Depends(get_mars_tenant_resolver)],
) -> MarsContext:
    """Validate the Authorization header and return the resolved context.

    HTTP mapping:
    - 401 Unauthorized: missing/invalid/expired bearer
    - 503 Service Unavailable: MARS /me network failure (transient)
    - 500: unexpected MarsApiError
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        claims = await validator.validate(token)
    except MarsAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        return await resolver.resolve(claims, token)
    except MarsAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except MarsApiError as exc:
        # MARS unreachable / 5xx → 503 so the client knows it's transient
        logger.warning("MARS /me failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MARS upstream unavailable",
        ) from exc


# ── module gating ──────────────────────────────────────────────────


def require_module_access(module_key: str) -> Callable:
    """Factory: returns a dep that also ensures the tenant has `module_key`.

    Usage in a route:
        @router.post("/autopilot/run",
                     dependencies=[Depends(require_module_access("noise"))])

    or:
        ctx: MarsContext = Depends(require_module_access("noise"))

    Returns 402 Payment Required if the module isn't in the tenant's
    enabled_modules list. This matches the MARS client's 402 mapping
    so the same status code is surfaced whether the check fires here
    or upstream.
    """

    async def dep(
        ctx: Annotated[MarsContext, Depends(require_mars_context)],
        client: Annotated[MarsApiClient, Depends(get_mars_client)],
    ) -> MarsContext:
        # Fast path: JWT enabled_modules list contains the module
        if module_key in ctx.enabled_modules:
            return ctx

        # Slow path: confirm with MARS (entitlement may have changed)
        try:
            result = await client.verify_module(ctx.access_token, module_key)
        except MarsPaymentRequiredError as exc:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Module '{module_key}' not purchased for tenant",
            ) from exc
        except MarsApiError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MARS upstream unavailable",
            ) from exc

        if not result.enabled:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=result.reason or f"Module '{module_key}' not enabled",
            )
        return ctx

    dep.__name__ = f"require_module_access__{module_key}"
    return dep
