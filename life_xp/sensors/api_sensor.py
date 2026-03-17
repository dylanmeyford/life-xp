"""API-based sensor — calls an HTTP endpoint and extracts data."""

from __future__ import annotations

from typing import Any

import httpx

from life_xp.sensors.base import Sensor, SensorRegistry


@SensorRegistry.register("api")
class APISensor(Sensor):
    """Fetches data from an HTTP API."""

    async def read(self) -> dict[str, Any]:
        url = self.config.get("url", "")
        method = self.config.get("method", "GET").upper()
        headers = self.config.get("headers", {})
        response_path = self.config.get("response_path", "")

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.request(method, url, headers=headers)
            resp.raise_for_status()

            if "json" in resp.headers.get("content-type", ""):
                data = resp.json()
                # Navigate to nested value
                if response_path:
                    for key in response_path.split("."):
                        if isinstance(data, dict):
                            data = data.get(key, data)
                        elif isinstance(data, list) and key.isdigit():
                            data = data[int(key)]
                return {"value": str(data)[:500], "source": "api"}
            else:
                return {"value": resp.text[:500], "source": "api"}
