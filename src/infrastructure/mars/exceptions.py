"""Exceptions raised by the MARS integration layer.

These map to HTTP status codes returned by the MARS API and allow
FastAPI dependencies / route handlers to translate them to appropriate
client-facing responses without leaking upstream details.
"""
from __future__ import annotations


class MarsApiError(Exception):
    """Base class — raised for any unexpected response from MARS."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        payload: dict | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


class MarsAuthError(MarsApiError):
    """401/403 — invalid or expired bearer token."""


class MarsNotFoundError(MarsApiError):
    """404 — resource does not exist upstream."""


class MarsConflictError(MarsApiError):
    """409 — optimistic lock / version mismatch."""


class MarsPaymentRequiredError(MarsApiError):
    """402 — tenant has not purchased the requested module."""


class MarsUnavailableError(MarsApiError):
    """5xx / connection failure / timeout exhausted."""


class MarsValidationError(MarsApiError):
    """422 / unprocessable entity — MARS rejected our payload."""
