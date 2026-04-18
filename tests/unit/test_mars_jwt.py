"""Unit tests for MarsJwtValidator.

Covers both RS256 (mocked JWKS) and HS256 (shared secret) modes,
plus error paths (expired, wrong aud/iss, missing kid, unknown kid,
bad signature, JWKS fetch failure).
"""

from __future__ import annotations

import json
import time
import uuid

import httpx
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.infrastructure.mars.exceptions import MarsAuthError
from src.infrastructure.mars.jwt_validator import MarsJwtValidator

ISSUER = "mars-core"
AUDIENCE = "mars-module-noise"
HS_SECRET = "dev-shared-secret-32chars-xxxxxxx"


# ── helpers ─────────────────────────────────────────────────────────


def _make_rsa_keypair() -> tuple[Any, str]:  # noqa: F821
    """Generate an RSA keypair; return (private_key_pem, public_jwk_json)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def _pub_pem_to_jwk(pub_pem: str, kid: str) -> dict:
    """Convert a PEM public key into a JWK dict (via PyJWT)."""
    from jwt.algorithms import RSAAlgorithm

    key = serialization.load_pem_public_key(pub_pem.encode())
    jwk_json = RSAAlgorithm.to_jwk(key)
    jwk = json.loads(jwk_json) if isinstance(jwk_json, str) else dict(jwk_json)
    jwk["kid"] = kid
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"
    return jwk


def _valid_payload(**over) -> dict:
    now = int(time.time())
    base = {
        "sub": str(uuid.uuid4()),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 300,
        "email": "user@example.com",
        "tenant_id": str(uuid.uuid4()),
        "enabled_modules": ["noise", "vibrations"],
    }
    base.update(over)
    return base


def _make_rs256_token(private_pem: str, payload: dict, kid: str) -> str:
    return pyjwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": kid})


def _make_hs256_token(payload: dict, secret: str = HS_SECRET) -> str:
    return pyjwt.encode(payload, secret, algorithm="HS256")


# ── HS256 mode ──────────────────────────────────────────────────────


async def test_hs256_valid_token():
    v = MarsJwtValidator(algorithm="HS256", issuer=ISSUER, audience=AUDIENCE, hs256_secret=HS_SECRET)
    payload = _valid_payload()
    token = _make_hs256_token(payload)
    claims = await v.validate(token)
    assert str(claims.user_id) == payload["sub"]
    assert str(claims.tenant_id) == payload["tenant_id"]
    assert claims.email == "user@example.com"
    assert "noise" in claims.enabled_modules


async def test_hs256_expired_token():
    v = MarsJwtValidator(algorithm="HS256", issuer=ISSUER, audience=AUDIENCE, hs256_secret=HS_SECRET)
    token = _make_hs256_token(_valid_payload(exp=int(time.time()) - 10))
    with pytest.raises(MarsAuthError, match="expired"):
        await v.validate(token)


async def test_hs256_wrong_issuer():
    v = MarsJwtValidator(algorithm="HS256", issuer=ISSUER, audience=AUDIENCE, hs256_secret=HS_SECRET)
    token = _make_hs256_token(_valid_payload(iss="other"))
    with pytest.raises(MarsAuthError, match="issuer mismatch"):
        await v.validate(token)


async def test_hs256_wrong_audience():
    v = MarsJwtValidator(algorithm="HS256", issuer=ISSUER, audience=AUDIENCE, hs256_secret=HS_SECRET)
    token = _make_hs256_token(_valid_payload(aud="other"))
    with pytest.raises(MarsAuthError, match="audience mismatch"):
        await v.validate(token)


async def test_hs256_bad_signature():
    v = MarsJwtValidator(algorithm="HS256", issuer=ISSUER, audience=AUDIENCE, hs256_secret=HS_SECRET)
    token = _make_hs256_token(_valid_payload(), secret="wrong-secret-32chars-xxxxxxxxxxxx")
    with pytest.raises(MarsAuthError, match="signature"):
        await v.validate(token)


async def test_hs256_missing_sub():
    v = MarsJwtValidator(algorithm="HS256", issuer=ISSUER, audience=AUDIENCE, hs256_secret=HS_SECRET)
    payload = _valid_payload()
    del payload["sub"]
    token = _make_hs256_token(payload)
    with pytest.raises(MarsAuthError, match="sub/userId"):
        await v.validate(token)


async def test_hs256_malformed_token():
    v = MarsJwtValidator(algorithm="HS256", issuer=ISSUER, audience=AUDIENCE, hs256_secret=HS_SECRET)
    with pytest.raises(MarsAuthError):
        await v.validate("not.a.jwt")


async def test_hs256_empty_token():
    v = MarsJwtValidator(algorithm="HS256", issuer=ISSUER, audience=AUDIENCE, hs256_secret=HS_SECRET)
    with pytest.raises(MarsAuthError, match="Missing"):
        await v.validate("")


async def test_hs256_camelcase_claims_supported():
    v = MarsJwtValidator(algorithm="HS256", issuer=ISSUER, audience=AUDIENCE, hs256_secret=HS_SECRET)
    payload = {
        "userId": str(uuid.uuid4()),
        "tenantId": str(uuid.uuid4()),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
        "enabledModules": ["noise"],
        "email": "u@e.com",
    }
    # PyJWT requires 'sub' or we add it as fallback; test userId camelCase
    payload["sub"] = payload["userId"]  # PyJWT sub is needed; our validator accepts userId
    token = _make_hs256_token(payload)
    claims = await v.validate(token)
    assert claims.enabled_modules == ["noise"]


# ── RS256 mode with mocked JWKS ─────────────────────────────────────


async def test_rs256_valid_token_with_mocked_jwks():
    private_pem, public_pem = _make_rsa_keypair()
    kid = "key-1"
    jwk = _pub_pem_to_jwk(public_pem, kid)

    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json={"keys": [jwk]})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    v = MarsJwtValidator(
        algorithm="RS256",
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://mars.test/.well-known/jwks.json",
        http_client=http,
    )
    try:
        payload = _valid_payload()
        token = _make_rs256_token(private_pem, payload, kid)

        claims = await v.validate(token)
        assert str(claims.user_id) == payload["sub"]
        assert call_count["n"] == 1  # JWKS fetched

        # Second call should hit cache, not fetch again
        await v.validate(token)
        assert call_count["n"] == 1
    finally:
        await http.aclose()


async def test_rs256_unknown_kid_triggers_refresh_then_raises():
    private_pem, public_pem = _make_rsa_keypair()
    jwk = _pub_pem_to_jwk(public_pem, "key-A")

    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json={"keys": [jwk]})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    v = MarsJwtValidator(
        algorithm="RS256",
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://mars.test/.well-known/jwks.json",
        http_client=http,
    )
    try:
        # Sign token with "key-X" but JWKS only has "key-A"
        token = _make_rs256_token(private_pem, _valid_payload(), "key-X")
        with pytest.raises(MarsAuthError, match="Unknown signing key"):
            await v.validate(token)
        assert call_count["n"] == 1  # JWKS refreshed once
    finally:
        await http.aclose()


async def test_rs256_missing_kid_header():
    _, public_pem = _make_rsa_keypair()
    jwk = _pub_pem_to_jwk(public_pem, "key-1")

    def handler(request):
        return httpx.Response(200, json={"keys": [jwk]})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    v = MarsJwtValidator(
        algorithm="RS256",
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://mars.test/.well-known/jwks.json",
        http_client=http,
    )
    try:
        # Manually craft a token without kid — use HS256 so it doesn't need key
        # but give it a non-RS256 signature; validator reads header first
        token = pyjwt.encode(_valid_payload(), "x", algorithm="HS256")  # no kid header
        with pytest.raises(MarsAuthError, match="'kid'"):
            await v.validate(token)
    finally:
        await http.aclose()


async def test_rs256_jwks_fetch_failure():
    def handler(request):
        return httpx.Response(503, text="boom")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    v = MarsJwtValidator(
        algorithm="RS256",
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://mars.test/.well-known/jwks.json",
        http_client=http,
    )
    try:
        private_pem, _ = _make_rsa_keypair()
        token = _make_rs256_token(private_pem, _valid_payload(), "key-1")
        with pytest.raises(MarsAuthError, match="fetch JWKS"):
            await v.validate(token)
    finally:
        await http.aclose()


async def test_rs256_jwks_empty_keys_list():
    def handler(request):
        return httpx.Response(200, json={"keys": []})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    v = MarsJwtValidator(
        algorithm="RS256",
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://mars.test/.well-known/jwks.json",
        http_client=http,
    )
    try:
        private_pem, _ = _make_rsa_keypair()
        token = _make_rs256_token(private_pem, _valid_payload(), "key-1")
        with pytest.raises(MarsAuthError, match="no usable keys"):
            await v.validate(token)
    finally:
        await http.aclose()


# ── construction validation ─────────────────────────────────────────


def test_rs256_requires_jwks_url():
    with pytest.raises(ValueError, match="jwks_url required"):
        MarsJwtValidator(algorithm="RS256", issuer=ISSUER, audience=AUDIENCE)


def test_hs256_requires_secret():
    with pytest.raises(ValueError, match="hs256_secret required"):
        MarsJwtValidator(algorithm="HS256", issuer=ISSUER, audience=AUDIENCE)


def test_unsupported_algorithm():
    with pytest.raises(ValueError, match="Unsupported algorithm"):
        MarsJwtValidator(algorithm="ES256", issuer=ISSUER, audience=AUDIENCE, hs256_secret="x")


# Type import shim
from typing import Any  # noqa: E402
