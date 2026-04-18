"""Locust load profile for MARS DVR Rumore hot endpoints.

Run against a local or staging instance:

    locust -f tests/load/locustfile.py --host http://localhost:8000

Weights are tuned to mirror the frontend's real traffic mix: health
checks dominate (LB probes), context listing is a user-driven read,
catalog is a lookup helper, and context creation is the rare write.
"""

from __future__ import annotations

import os
import uuid

from locust import HttpUser, between, task

API_PREFIX = "/api/v1/noise"


class NoisePluginUser(HttpUser):
    """Simulated consultant browsing + occasionally bootstrapping."""

    wait_time = between(0.5, 2.5)

    def on_start(self) -> None:
        token = os.environ.get("LOCUST_JWT", "")
        if token:
            self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(10)
    def health_ready(self) -> None:
        self.client.get("/health/ready", name="GET /health/ready")

    @task(5)
    def list_contexts(self) -> None:
        self.client.get(f"{API_PREFIX}/contexts", name="GET /contexts")

    @task(3)
    def list_noise_sources(self) -> None:
        self.client.get(
            f"{API_PREFIX}/catalog/noise-sources",
            name="GET /catalog/noise-sources",
        )

    @task(1)
    def bootstrap_context(self) -> None:
        payload = {
            "company_id": str(uuid.uuid4()),
            "dvr_id": str(uuid.uuid4()),
            "force_sync": False,
        }
        self.client.post(
            f"{API_PREFIX}/contexts",
            json=payload,
            name="POST /contexts",
        )
