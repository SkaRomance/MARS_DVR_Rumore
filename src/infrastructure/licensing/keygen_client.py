import httpx


class KeygenClient:
    def __init__(self, api_url: str, account_id: str, admin_token: str):
        self.api_url = api_url.rstrip("/")
        self.account_id = account_id
        self.admin_token = admin_token
        self._client: httpx.AsyncClient | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.admin_token}",
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def validate_license(self, license_id: str) -> dict | None:
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.api_url}/accounts/{self.account_id}/licenses/{license_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, httpx.InvalidURL):
            return None

    async def activate_license(self, license_id: str, fingerprint: str) -> dict | None:
        client = await self._get_client()
        try:
            payload = {
                "data": {
                    "type": "machines",
                    "attributes": {"fingerprint": fingerprint},
                    "relationships": {
                        "license": {
                            "data": {"type": "licenses", "id": license_id}
                        }
                    },
                }
            }
            resp = await client.post(
                f"{self.api_url}/accounts/{self.account_id}/machines",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, httpx.InvalidURL):
            return None

    async def deactivate_license(self, machine_id: str) -> dict | None:
        client = await self._get_client()
        try:
            resp = await client.delete(
                f"{self.api_url}/accounts/{self.account_id}/machines/{machine_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return {"deleted": True}
        except (httpx.HTTPError, httpx.InvalidURL):
            return None

    async def check_entitlements(self, license_id: str) -> list[dict] | None:
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.api_url}/accounts/{self.account_id}/licenses/{license_id}/entitlements",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data if isinstance(data, list) else []
        except (httpx.HTTPError, httpx.InvalidURL):
            return None

    async def checkout_license(self, license_id: str, metadata: dict) -> dict | None:
        client = await self._get_client()
        try:
            payload = {
                "meta": {"metadata": metadata}
            }
            resp = await client.post(
                f"{self.api_url}/accounts/{self.account_id}/licenses/{license_id}/actions/check-out",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, httpx.InvalidURL):
            return None