"""JWT validator for MARS-issued access tokens.

Two authentication modes (switched by settings.mars_jwt_algorithm):

- **RS256 (production)**: MARS signs tokens with its private key and
  publishes the corresponding public key via JWKS at mars_jwks_url.
  We fetch the JWKS lazily, cache keys by `kid` with TTL, and verify
  signatures using the public key matching the token's kid header.
  No shared secret required.

- **HS256 (dev / tests)**: MARS and we share a secret
  (mars_jwt_hs256_secret). Simpler setup but requires rotating the
  secret when compromised.

Validation enforces:
- signature (per algorithm)
- expiry (`exp`)
- issuer (`iss`) matches settings.mars_issuer
- audience (`aud`) matches settings.mars_audience

Returns a `MarsJwtClaims` dataclass. Any validation failure raises
`MarsAuthError` with an actionable message — callers typically
translate this to HTTP 401.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt as pyjwt
from jwt.algorithms import RSAAlgorithm

from src.infrastructure.mars.exceptions import MarsAuthError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarsJwtClaims:
    """Decoded claims from a validated MARS JWT."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID | None
    email: str | None
    enabled_modules: list[str] = field(default_factory=list)
    issuer: str = ""
    audience: str = ""
    expires_at: int = 0  # epoch seconds
    raw_claims: dict[str, Any] = field(default_factory=dict)


class _JwksCache:
    """In-memory TTL cache for JWKS public keys (keyed by `kid`)."""

    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._keys: dict[str, Any] = {}
        self._fetched_at: float = 0.0

    def is_fresh(self) -> bool:
        return self._keys and (time.monotonic() - self._fetched_at) < self._ttl

    def get(self, kid: str) -> Any | None:
        return self._keys.get(kid) if self.is_fresh() else None

    def replace(self, keys: dict[str, Any]) -> None:
        self._keys = keys
        self._fetched_at = time.monotonic()

    def invalidate(self) -> None:
        self._keys = {}
        self._fetched_at = 0.0


class MarsJwtValidator:
    """Validates JWTs issued by MARS.

    Instantiate once per app (FastAPI dependency singleton). Thread-safe
    for read workloads because httpx.AsyncClient + dict access are
    safe, and JWKS cache is refreshed via a single awaited call.
    """

    def __init__(
        self,
        algorithm: str,
        issuer: str,
        audience: str,
        *,
        jwks_url: str | None = None,
        hs256_secret: str | None = None,
        jwks_cache_ttl: int = 3600,
        http_client: httpx.AsyncClient | None = None,
    ):
        if algorithm not in {"RS256", "HS256"}:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        if algorithm == "RS256" and not jwks_url:
            raise ValueError("jwks_url required when algorithm=RS256")
        if algorithm == "HS256" and not hs256_secret:
            raise ValueError("hs256_secret required when algorithm=HS256")

        self._algorithm = algorithm
        self._issuer = issuer
        self._audience = audience
        self._jwks_url = jwks_url
        self._hs256_secret = hs256_secret
        self._cache = _JwksCache(jwks_cache_ttl)
        self._http = http_client  # may be None in HS256 mode
        self._owns_http = False
        if algorithm == "RS256" and http_client is None:
            self._http = httpx.AsyncClient(timeout=10.0)
            self._owns_http = True

    async def close(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def validate(self, token: str) -> MarsJwtClaims:
        """Verify signature + claims, return decoded claims.

        Raises MarsAuthError on any failure.
        """
        if not token or not isinstance(token, str):
            raise MarsAuthError("Missing or malformed token")

        try:
            unverified_header = pyjwt.get_unverified_header(token)
        except pyjwt.PyJWTError as exc:
            raise MarsAuthError(f"Invalid JWT header: {exc}") from exc

        if self._algorithm == "RS256":
            key = await self._resolve_rsa_key(unverified_header.get("kid"))
            algorithms = ["RS256"]
        else:
            key = self._hs256_secret
            algorithms = ["HS256"]

        try:
            payload = pyjwt.decode(
                token,
                key=key,
                algorithms=algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iss", "aud"]},
            )
        except pyjwt.ExpiredSignatureError as exc:
            raise MarsAuthError("Token expired") from exc
        except pyjwt.InvalidAudienceError as exc:
            raise MarsAuthError(f"Token audience mismatch (expected {self._audience})") from exc
        except pyjwt.InvalidIssuerError as exc:
            raise MarsAuthError(f"Token issuer mismatch (expected {self._issuer})") from exc
        except pyjwt.InvalidSignatureError as exc:
            raise MarsAuthError("Invalid token signature") from exc
        except pyjwt.PyJWTError as exc:
            raise MarsAuthError(f"Invalid token: {exc}") from exc

        return self._claims_from_payload(payload)

    # ── JWKS resolution ────────────────────────────────────────────

    async def _resolve_rsa_key(self, kid: str | None) -> Any:
        """Return the RSA public key matching `kid`, fetching JWKS if needed."""
        if not kid:
            raise MarsAuthError("Token header missing 'kid' — cannot resolve key")

        cached = self._cache.get(kid)
        if cached is not None:
            return cached

        await self._refresh_jwks()
        cached = self._cache.get(kid)
        if cached is None:
            # kid not present after refresh → token signed with retired key
            raise MarsAuthError(f"Unknown signing key (kid={kid})")
        return cached

    async def _refresh_jwks(self) -> None:
        assert self._http is not None, "HTTP client required in RS256 mode"
        assert self._jwks_url, "jwks_url required"
        try:
            response = await self._http.get(self._jwks_url)
            response.raise_for_status()
        except (httpx.HTTPError, httpx.TransportError) as exc:
            raise MarsAuthError(f"Failed to fetch JWKS: {exc}") from exc

        try:
            jwks = response.json()
        except Exception as exc:
            raise MarsAuthError(f"Malformed JWKS response: {exc}") from exc

        keys_list = jwks.get("keys", []) if isinstance(jwks, dict) else []
        new_keys: dict[str, Any] = {}
        for jwk in keys_list:
            if not isinstance(jwk, dict):
                continue
            kid = jwk.get("kid")
            if not kid:
                continue
            try:
                new_keys[kid] = RSAAlgorithm.from_jwk(jwk)
            except Exception as exc:
                logger.warning("Skipping malformed JWK kid=%s: %s", kid, exc)

        if not new_keys:
            raise MarsAuthError("JWKS contained no usable keys")

        self._cache.replace(new_keys)
        logger.info("Refreshed MARS JWKS (%d keys)", len(new_keys))

    # ── claims shaping ─────────────────────────────────────────────

    @staticmethod
    def _claims_from_payload(payload: dict[str, Any]) -> MarsJwtClaims:
        user_id_raw = payload.get("sub") or payload.get("userId")
        if not user_id_raw:
            raise MarsAuthError("Token missing sub/userId claim")
        try:
            user_id = uuid.UUID(str(user_id_raw))
        except (ValueError, TypeError) as exc:
            raise MarsAuthError(f"Invalid sub/userId UUID: {user_id_raw}") from exc

        tenant_raw = payload.get("tenant_id") or payload.get("tenantId")
        tenant_id: uuid.UUID | None = None
        if tenant_raw:
            try:
                tenant_id = uuid.UUID(str(tenant_raw))
            except (ValueError, TypeError):
                logger.warning("Ignoring non-UUID tenant claim: %r", tenant_raw)

        aud = payload.get("aud")
        if isinstance(aud, list):
            aud_str = aud[0] if aud else ""
        else:
            aud_str = str(aud) if aud is not None else ""

        modules_raw = payload.get("enabled_modules") or payload.get("enabledModules") or []
        modules = [str(m) for m in modules_raw if isinstance(m, str)]

        return MarsJwtClaims(
            user_id=user_id,
            tenant_id=tenant_id,
            email=payload.get("email"),
            enabled_modules=modules,
            issuer=str(payload.get("iss", "")),
            audience=aud_str,
            expires_at=int(payload.get("exp", 0)),
            raw_claims=payload,
        )
