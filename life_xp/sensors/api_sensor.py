"""API-based sensor — calls an HTTP endpoint and extracts data."""

from __future__ import annotations

import re
from typing import Any

import httpx

from life_xp.sensors.base import Sensor, SensorRegistry


def extract_path(data: Any, path: str) -> Any:
    """
    Traverse a nested JSON structure using a dot-separated path that supports
    array indexing, e.g. "activities-steps[0].value" or "results.0.score".
    """
    if not path:
        return data
    # Tokenise: split on '.' then further split tokens containing '[N]'
    tokens: list[str | int] = []
    for part in path.split("."):
        bracket = re.match(r"^(.*?)\[(\d+)\]$", part)
        if bracket:
            key, idx = bracket.group(1), int(bracket.group(2))
            if key:
                tokens.append(key)
            tokens.append(idx)
        elif part.isdigit():
            tokens.append(int(part))
        else:
            tokens.append(part)

    for token in tokens:
        try:
            if isinstance(token, int):
                data = data[token]
            elif isinstance(data, dict):
                data = data[token]
            else:
                break
        except (KeyError, IndexError, TypeError):
            break
    return data


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
                if response_path:
                    data = extract_path(data, response_path)
                return {"value": str(data)[:500], "source": "api"}
            else:
                return {"value": resp.text[:500], "source": "api"}
