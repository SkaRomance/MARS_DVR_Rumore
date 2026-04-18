"""Async HTTP client for the MARS API.

Responsibilities:
- Bearer token authentication (token supplied per call, not stored)
- Retry with exponential backoff on 5xx + transport errors
- Typed Pydantic responses
- Status-code -> structured exception translation

Design rationale:
- Token is passed per call so the same client instance can serve
  multiple concurrent requests from different users without mixing
  auth state.
- Retry limit defaults to 3 with 0.5s / 1s / 2s backoff. Transport
  errors (connection refused, DNS, read timeout) retry. 4xx do NOT
  retry (caller bug, no amount of retry fixes it).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import httpx

from src.infrastructure.mars.exceptions import (
    MarsApiError,
    MarsAuthError,
    MarsConflictError,
    MarsNotFoundError,
    MarsPaymentRequiredError,
    MarsUnavailableError,
    MarsValidationError,
)
from src.infrastructure.mars.types import (
    MarsDvrRevisionResponse,
    MarsMeResponse,
    MarsModuleSessionResponse,
    MarsModuleVerifyResponse,
)

logger = logging.getLogger(__name__)


class MarsApiClient:
    """Async client for calling the MARS NestJS API.

    Usage:
        async with MarsApiClient(base_url="https://app.mars.local") as cli:
            me = await cli.get_me(token)
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": "MARS-DVR-Rumore/0.1"},
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> MarsApiClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    # ── internal request plumbing ──────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        token: str,
        *,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """Send a request, retrying on transport errors and 5xx.

        Caller handles 4xx via `_raise_for_status`.
        """
        merged_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            merged_headers.update(headers)

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=path,
                    json=json,
                    headers=merged_headers,
                )
                if 500 <= response.status_code < 600:
                    if attempt < self._max_retries:
                        backoff = 0.5 * (2**attempt)
                        logger.warning(
                            "MARS %s %s -> %d, retry in %.1fs (attempt %d/%d)",
                            method,
                            path,
                            response.status_code,
                            backoff,
                            attempt + 1,
                            self._max_retries,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    # exhausted retries
                    raise MarsUnavailableError(
                        f"MARS 5xx after {self._max_retries} retries: {response.status_code}",
                        status_code=response.status_code,
                        payload=self._safe_json(response),
                    )
                return response
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    backoff = 0.5 * (2**attempt)
                    logger.warning(
                        "MARS %s %s transport error: %s, retry in %.1fs (attempt %d/%d)",
                        method,
                        path,
                        exc,
                        backoff,
                        attempt + 1,
                        self._max_retries,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise MarsUnavailableError(f"MARS transport error after {self._max_retries} retries: {exc}") from exc

        # Should never reach here — loop always returns or raises
        raise MarsUnavailableError(f"MARS request exhausted retries: {last_exc}")

    def _raise_for_status(self, response: httpx.Response, context: str) -> None:
        """Map HTTP status codes to structured MARS exceptions."""
        status = response.status_code
        if 200 <= status < 300:
            return

        payload = self._safe_json(response)
        message = payload.get("message") or payload.get("detail") or response.text[:200]

        if status == 401 or status == 403:
            raise MarsAuthError(f"{context}: auth failed ({status})", status, payload)
        if status == 402:
            raise MarsPaymentRequiredError(f"{context}: module not purchased", status, payload)
        if status == 404:
            raise MarsNotFoundError(f"{context}: not found", status, payload)
        if status == 409:
            raise MarsConflictError(f"{context}: conflict", status, payload)
        if status == 422:
            raise MarsValidationError(f"{context}: validation failed", status, payload)
        raise MarsApiError(f"{context}: {message} ({status})", status, payload)

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict:
        try:
            data = response.json()
            return data if isinstance(data, dict) else {"raw": data}
        except Exception:
            return {}

    # ── public API ─────────────────────────────────────────────────

    async def get_me(self, token: str) -> MarsMeResponse:
        """GET /me — current user + tenant + enabled modules."""
        response = await self._request("GET", "/me", token)
        self._raise_for_status(response, "get_me")
        return MarsMeResponse.model_validate(response.json())

    async def verify_module(self, token: str, module_key: str) -> MarsModuleVerifyResponse:
        """POST /modules/verify — is this module enabled for the caller's tenant?"""
        response = await self._request("POST", "/modules/verify", token, json={"moduleKey": module_key})
        self._raise_for_status(response, f"verify_module({module_key})")
        return MarsModuleVerifyResponse.model_validate(response.json())

    async def get_dvr_revision(
        self,
        token: str,
        document_id: uuid.UUID | str,
        revision_id: uuid.UUID | str | None = None,
    ) -> MarsDvrRevisionResponse:
        """GET /dvr-documents/{doc}/revisions/{rev} — DVR snapshot.

        If revision_id is None, returns latest published revision.
        """
        if revision_id is None:
            path = f"/dvr-documents/{document_id}/revisions/latest"
        else:
            path = f"/dvr-documents/{document_id}/revisions/{revision_id}"
        response = await self._request("GET", path, token)
        self._raise_for_status(response, f"get_dvr_revision({document_id}, {revision_id})")
        return MarsDvrRevisionResponse.model_validate(response.json())

    async def put_module_extensions(
        self,
        token: str,
        document_id: uuid.UUID | str,
        revision_id: uuid.UUID | str,
        module_key: str,
        payload: dict[str, Any],
        *,
        if_match_version: int | None = None,
    ) -> MarsDvrRevisionResponse:
        """PUT /dvr-documents/{doc}/revisions/{rev}/module-extensions/{moduleKey}

        Writes module-specific payload into the DVR snapshot's
        `module_extensions.<moduleKey>` namespace. If `if_match_version`
        is supplied, sends `If-Match: <version>` header for optimistic
        concurrency control; mismatches raise MarsConflictError.
        """
        headers = {}
        if if_match_version is not None:
            headers["If-Match"] = str(if_match_version)
        path = f"/dvr-documents/{document_id}/revisions/{revision_id}/module-extensions/{module_key}"
        response = await self._request("PUT", path, token, json=payload, headers=headers)
        self._raise_for_status(response, f"put_module_extensions({document_id}, {module_key})")
        return MarsDvrRevisionResponse.model_validate(response.json())

    async def register_module_session(
        self,
        token: str,
        document_id: uuid.UUID | str,
        revision_id: uuid.UUID | str,
        module_key: str,
    ) -> MarsModuleSessionResponse:
        """POST /modules/sessions/register — tells MARS a module session started.

        Used for audit (MARS logs who opened which module when) and
        optionally for concurrency control (single editor per revision).
        """
        response = await self._request(
            "POST",
            "/modules/sessions/register",
            token,
            json={
                "dvrDocumentId": str(document_id),
                "revisionId": str(revision_id),
                "moduleKey": module_key,
            },
        )
        self._raise_for_status(response, "register_module_session")
        return MarsModuleSessionResponse.model_validate(response.json())
